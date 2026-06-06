import os
import json
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Import database models
from database import Invoice, ChatHistory

load_dotenv()

class AIAssistant:
    @classmethod
    def get_response(
        cls, 
        user_message: str, 
        db: Session, 
        gemini_key: Optional[str] = None, 
        openai_key: Optional[str] = None
    ) -> str:
        """
        Processes the user message, builds the context from database records,
        and generates a reply using Gemini or OpenAI (or a mock fallback).
        """
        g_key = gemini_key or os.getenv("GEMINI_API_KEY")
        o_key = openai_key or os.getenv("OPENAI_API_KEY")

        # 1. Fetch all invoices from the database to build context
        invoices = db.query(Invoice).all()
        
        # Build a concise structured representation of the financial records
        records_context = []
        for inv in invoices:
            records_context.append({
                "invoice_number": inv.invoice_number,
                "vendor_name": inv.vendor_name,
                "invoice_date": inv.invoice_date.strftime("%Y-%m-%d") if inv.invoice_date else "N/A",
                "taxable_amount": inv.taxable_amount,
                "cgst": inv.cgst,
                "sgst_utgst": inv.sgst_utgst,
                "igst": inv.igst,
                "total_amount": inv.total_amount,
                "expense_category": inv.expense_category,
                "gstin_vendor": inv.gstin_vendor,
                "gstin_recipient": inv.gstin_recipient,
                "status": inv.status
            })
            
        context_str = json.dumps(records_context, indent=2)

        # 2. Retrieve recent chat history for conversation continuity (last 5 messages)
        history = db.query(ChatHistory).order_by(ChatHistory.id.desc()).limit(5).all()
        history = list(reversed(history))
        
        # 3. If no keys are configured, use a smart mock response generator
        if not g_key and not o_key:
            return cls._generate_mock_response(user_message, records_context)

        # Build prompt
        system_prompt = (
            "You are an AI Invoice and GST Assistant for a small Indian business. "
            "You have access to all the parsed invoices in the database. "
            "Analyze the database context provided below and answer the user's questions. "
            "Be precise, clear, and refer directly to the numerical details in the invoices. "
            "Use currency formatting in Indian Rupees (INR) or simple format. "
            "If the user asks for calculations, perform them step-by-step. "
            "If there is no data matching the query, state it clearly.\n\n"
            f"DATABASE CONTEXT (All Invoices):\n{context_str}\n\n"
            "Instructions:\n"
            "- Answer in a helpful, business-focused tone.\n"
            "- If they ask how much they spent in a certain category, sum it up.\n"
            "- If they ask about GST or taxes, refer to CGST, SGST, IGST."
        )

        if g_key:
            try:
                return cls._generate_with_gemini(user_message, system_prompt, history, g_key)
            except Exception as e:
                print(f"Assistant Gemini call failed: {e}. Trying OpenAI if key exists.")
                if not o_key:
                    return f"Error using Gemini API: {str(e)}"
                    
        if o_key:
            try:
                return cls._generate_with_openai(user_message, system_prompt, history, o_key)
            except Exception as e:
                return f"Error using OpenAI API: {str(e)}"
                
        return cls._generate_mock_response(user_message, records_context)

    @classmethod
    def _generate_with_gemini(
        cls, 
        user_message: str, 
        system_prompt: str, 
        history: List[ChatHistory], 
        api_key: str
    ) -> str:
        import google.generativeai as genai
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Build contents incorporating system prompt and conversation history
        contents = [
            f"{system_prompt}\n\n"
            "Here is the chat history so far:"
        ]
        
        for msg in history:
            contents.append(f"{msg.role.upper()}: {msg.content}")
            
        contents.append(f"USER: {user_message}")
        contents.append("ASSISTANT: ")
        
        response = model.generate_content(contents)
        return response.text

    @classmethod
    def _generate_with_openai(
        cls, 
        user_message: str, 
        system_prompt: str, 
        history: List[ChatHistory], 
        api_key: str
    ) -> str:
        from openai import OpenAI
        
        client = OpenAI(api_key=api_key)
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
            
        messages.append({"role": "user", "content": user_message})
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.2
        )
        
        return response.choices[0].message.content

    @classmethod
    def _generate_mock_response(cls, user_message: str, records: List[dict]) -> str:
        """A rule-based response generator for Demo Mode when no API keys are present."""
        msg = user_message.lower()
        
        # Standard Greeting
        if any(greet in msg for greet in ["hello", "hi", "hey"]):
            return (
                "👋 Hello! I am your AI Invoice & GST Assistant (currently running in Demo Mode).\n\n"
                "I can analyze your uploaded invoices and calculate tax, spend by categories, or detail vendor invoices.\n"
                "Try asking questions like:\n"
                "- *'How much did I spend on Transport?'*\n"
                "- *'What is my total GST tax credit?'*\n"
                "- *'How many invoices do I have?'*"
            )

        # Count invoices
        if "how many" in msg and "invoice" in msg:
            count = len(records)
            if count == 0:
                return "You currently have **0 invoices** in the database. Please upload some invoice images or PDFs to get started!"
            return f"You currently have **{count} invoice(s)** in the database."

        # Category spend calculations
        categories = ["transport", "inventory", "utilities", "office supplies", "meals & entertainment", "rent", "salaries", "others"]
        found_category = None
        for cat in categories:
            if cat in msg:
                found_category = cat
                break
                
        if found_category or "spend" in msg or "expense" in msg or "cost" in msg:
            if found_category:
                # Calculate for specific category
                cat_display = found_category.title()
                cat_invoices = [r for r in records if r["expense_category"].lower() == found_category]
                total = sum(r["total_amount"] for r in cat_invoices)
                taxable = sum(r["taxable_amount"] for r in cat_invoices)
                count = len(cat_invoices)
                
                if count == 0:
                    return f"I found **no invoices** categorized under **{cat_display}** in your records."
                return (
                    f"📂 **Category: {cat_display}**\n\n"
                    f"- **Total Spend:** ₹{total:,.2f} (including taxes)\n"
                    f"- **Taxable Amount:** ₹{taxable:,.2f}\n"
                    f"- **Number of Invoices:** {count}\n\n"
                    f"Let me know if you'd like a breakdown of these invoices!"
                )
            else:
                # Total spend across all
                total_all = sum(r["total_amount"] for r in records)
                taxable_all = sum(r["taxable_amount"] for r in records)
                count_all = len(records)
                
                if count_all == 0:
                    return "You haven't uploaded any invoices yet, so your total spend is ₹0.00."
                    
                # Breakdown by category
                cat_summary = {}
                for r in records:
                    cat = r["expense_category"]
                    cat_summary[cat] = cat_summary.get(cat, 0.0) + r["total_amount"]
                
                breakdown_str = "\n".join([f"- **{k}:** ₹{v:,.2f}" for k, v in cat_summary.items()])
                
                return (
                    f"📊 **Overall Spending Summary**\n\n"
                    f"- **Total Invoices Scanned:** {count_all}\n"
                    f"- **Total Spend (Gross):** ₹{total_all:,.2f}\n"
                    f"- **Total Taxable Amount:** ₹{taxable_all:,.2f}\n\n"
                    f"**Breakdown by Category:**\n{breakdown_str}"
                )

        # GST and tax queries
        if any(x in msg for x in ["gst", "tax", "cgst", "sgst", "igst", "credit", "itc"]):
            total_cgst = sum(r["cgst"] for r in records)
            total_sgst = sum(r["sgst_utgst"] for r in records)
            total_igst = sum(r["igst"] for r in records)
            total_tax = total_cgst + total_sgst + total_igst
            
            if len(records) == 0:
                return "You don't have any invoices uploaded yet, so your total GST is ₹0.00."
                
            return (
                f"🧾 **Indian GST & Tax Summary**\n\n"
                f"You have accumulated a total of **₹{total_tax:,.2f}** in input tax credits (ITC):\n"
                f"- **CGST (Central GST):** ₹{total_cgst:,.2f}\n"
                f"- **SGST/UTGST (State GST):** ₹{total_sgst:,.2f}\n"
                f"- **IGST (Integrated GST):** ₹{total_igst:,.2f}\n\n"
                f"These amounts can be claimed as Input Tax Credit (ITC) in your monthly GSTR-3B filings."
            )

        # Vendor specific search
        vendors = list(set([r["vendor_name"] for r in records if r["vendor_name"]]))
        found_vendor = None
        for v in vendors:
            if v.lower() in msg:
                found_vendor = v
                break
                
        if found_vendor:
            vendor_invoices = [r for r in records if r["vendor_name"] == found_vendor]
            total = sum(r["total_amount"] for r in vendor_invoices)
            count = len(vendor_invoices)
            
            list_str = "\n".join([f"- Bill #{r['invoice_number']} on {r['invoice_date']} for ₹{r['total_amount']:,.2f} (GSTIN: {r['gstin_vendor']})" for r in vendor_invoices])
            
            return (
                f"🏢 **Vendor: {found_vendor}**\n\n"
                f"I found **{count} invoice(s)** totaling **₹{total:,.2f}**:\n"
                f"{list_str}"
            )

        # Default fallback response
        return (
            "🤖 *[Demo Mode Response]*\n\n"
            "I couldn't quite map your question directly in Demo Mode. To get fully-featured AI responses that "
            "understand context, please enter your **Gemini API Key** or **OpenAI API Key** in the **Settings** tab!\n\n"
            "*(If you want to test calculations in Demo Mode, try using keywords like 'spend', 'GST', or 'Reliance' to activate simulated mock responses).*"
        )
