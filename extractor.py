import os
import io
import json
import base64
from typing import Tuple, Optional
from PIL import Image
import pypdf
from dotenv import load_dotenv

# Import our extraction schema
from schemas import ExtractedInvoice, ExtractedInvoiceItem

# Load environment variables
load_dotenv()

class InvoiceExtractor:
    @staticmethod
    def get_supported_extension(filename: str) -> bool:
        ext = filename.split(".")[-1].lower()
        return ext in ["pdf", "png", "jpg", "jpeg", "webp"]

    @staticmethod
    def extract_text_from_pdf(pdf_bytes: bytes) -> str:
        """Extract text from text-based PDFs using pypdf."""
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            reader = pypdf.PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return ""

    @classmethod
    def extract_invoice_data(
        cls, 
        file_bytes: bytes, 
        filename: str, 
        gemini_key: Optional[str] = None, 
        openai_key: Optional[str] = None
    ) -> Tuple[ExtractedInvoice, str]:
        """
        Main entry point for extraction.
        Returns:
            Tuple[ExtractedInvoice, raw_text_or_info]
        """
        # Determine API Keys from arguments or environment variables
        g_key = gemini_key or os.getenv("GEMINI_API_KEY")
        o_key = openai_key or os.getenv("OPENAI_API_KEY")
        
        ext = filename.split(".")[-1].lower()
        
        # 1. Check if mock mode is forced (no keys provided)
        if not g_key and not o_key:
            return cls._get_mock_data(filename)
            
        # 2. Extract context based on file type
        is_pdf = ext == "pdf"
        
        # If it's a PDF, we try to extract text first.
        pdf_text = ""
        if is_pdf:
            pdf_text = cls.extract_text_from_pdf(file_bytes)
            
        # 3. Call AI depending on configuration and media type
        # Prefer Gemini (free tier & native multimodal)
        if g_key:
            try:
                return cls._extract_with_gemini(file_bytes, filename, pdf_text, g_key)
            except Exception as e:
                print(f"Gemini extraction failed: {e}. Falling back to OpenAI if key available or Mock.")
                if not o_key:
                    raise e
                    
        if o_key:
            try:
                return cls._extract_with_openai(file_bytes, filename, pdf_text, o_key)
            except Exception as e:
                print(f"OpenAI extraction failed: {e}")
                raise e
                
        return cls._get_mock_data(filename)

    @classmethod
    def _extract_with_gemini(
        cls, 
        file_bytes: bytes, 
        filename: str, 
        pdf_text: str, 
        api_key: str
    ) -> Tuple[ExtractedInvoice, str]:
        import google.generativeai as genai
        from google.generativeai.types import GenerateContentConfig
        
        genai.configure(api_key=api_key)
        
        # Choose model: gemini-1.5-flash is extremely fast and supports structured JSON outputs
        model_name = "gemini-1.5-flash"
        model = genai.GenerativeModel(model_name)
        
        # Prepare system prompt instructing GST rules and Indian context
        prompt = (
            "You are an expert Indian GST & Invoice parser. Analyze the provided invoice document "
            "and extract all fields accurately. Convert the date into YYYY-MM-DD. "
            "Identify the Vendor GSTIN and Recipient GSTIN. Breakdown the tax details into "
            "CGST, SGST/UTGST, IGST, and Taxable Amount. Categorize the invoice into one of the "
            "provided expense categories: 'Transport', 'Inventory', 'Utilities', 'Office Supplies', "
            "'Meals & Entertainment', 'Rent', 'Salaries', or 'Others'."
        )
        
        ext = filename.split(".")[-1].lower()
        
        # Build contents
        contents = []
        raw_info = ""
        
        if ext == "pdf":
            if pdf_text.strip():
                contents.append(f"{prompt}\n\nHere is the raw text extracted from the PDF:\n{pdf_text}")
                raw_info = pdf_text
            else:
                # Scanned PDF without text: Gemini 1.5 API can accept raw PDF bytes directly!
                contents.append({
                    "mime_type": "application/pdf",
                    "data": file_bytes
                })
                contents.append(prompt)
                raw_info = "[Scanned PDF - Visual Analysis]"
        else:
            # Image files
            image = Image.open(io.BytesIO(file_bytes))
            contents.append(image)
            contents.append(prompt)
            raw_info = f"[Image File: {filename} - Visual Analysis]"

        # Call Gemini with Structured Outputs
        # Pydantic schema is passed to response_schema
        config = GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtractedInvoice,
            temperature=0.1
        )
        
        response = model.generate_content(
            contents,
            generation_config=config
        )
        
        # Parse output JSON
        data = json.loads(response.text)
        return ExtractedInvoice(**data), raw_info

    @classmethod
    def _extract_with_openai(
        cls, 
        file_bytes: bytes, 
        filename: str, 
        pdf_text: str, 
        api_key: str
    ) -> Tuple[ExtractedInvoice, str]:
        from openai import OpenAI
        
        client = OpenAI(api_key=api_key)
        ext = filename.split(".")[-1].lower()
        
        prompt = (
            "You are an expert Indian GST & Invoice parser. Analyze the provided invoice data "
            "and extract all fields accurately. Convert the date into YYYY-MM-DD. "
            "Identify the Vendor GSTIN and Recipient GSTIN. Breakdown the tax details into "
            "CGST, SGST/UTGST, IGST, and Taxable Amount. Categorize the invoice into one of the "
            "provided expense categories: 'Transport', 'Inventory', 'Utilities', 'Office Supplies', "
            "'Meals & Entertainment', 'Rent', 'Salaries', or 'Others'."
        )
        
        messages = [
            {"role": "system", "content": prompt}
        ]
        
        raw_info = ""
        
        # OpenAI requires base64 images for multimodal. For PDF, we send the text if available.
        if ext == "pdf":
            if pdf_text.strip():
                messages.append({"role": "user", "content": f"Invoice PDF Text:\n{pdf_text}"})
                raw_info = pdf_text
            else:
                # Scanned PDF, without local pdf2image we can't easily convert to base64 images here.
                # So we fail gracefully or warn.
                raise ValueError("Scanned PDF requires Gemini API key (which supports raw PDF upload) or text-based PDF.")
        else:
            # Convert image to base64
            base64_image = base64.b64encode(file_bytes).decode('utf-8')
            mime_type = f"image/{ext if ext != 'jpg' else 'jpeg'}"
            
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "content": "Here is the invoice image. Please parse it."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        }
                    }
                ]
            })
            raw_info = f"[Image File: {filename} - Visual Analysis]"

        # Call OpenAI with response_format matching Pydantic structure
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=messages,
            response_format=ExtractedInvoice,
            temperature=0.1
        )
        
        parsed_result = response.choices[0].message.parsed
        return parsed_result, raw_info

    @classmethod
    def _get_mock_data(cls, filename: str) -> Tuple[ExtractedInvoice, str]:
        """Generates realistic mock invoice data based on filename to support Demo Mode."""
        name_lower = filename.lower()
        
        # Setup defaults
        vendor = "Generic Vendor Pvt Ltd"
        inv_no = "INV-2026-001"
        inv_date = "2026-05-15"
        gstin_v = "27AAAAA1111A1Z1"  # Maharashtra GSTIN
        gstin_r = "07BBBBB2222B2Z2"  # Delhi GSTIN
        category = "Others"
        
        items = []
        taxable = 1000.0
        cgst = 0.0
        sgst = 0.0
        igst = 0.0
        
        if "reliance" in name_lower or "jio" in name_lower:
            vendor = "Reliance Retail Limited"
            inv_no = "RRL/MUM/98341"
            gstin_v = "27AAAAC5312R1Z5"
            category = "Inventory"
            items = [
                ExtractedInvoiceItem(description="Office Stationery Bundle", quantity=2.0, unit_price=250.0, amount=500.0, gst_rate=18.0),
                ExtractedInvoiceItem(description="Laser Printer Paper Reams", quantity=5.0, unit_price=200.0, amount=1000.0, gst_rate=18.0)
            ]
            # Total taxable is 1500
            taxable = 1500.0
            # 18% GST (CGST 9%, SGST 9% since Maharashtra to Maharashtra, assuming intra-state)
            cgst = 135.0
            sgst = 135.0
            igst = 0.0
            
        elif "uber" in name_lower or "ola" in name_lower or "travel" in name_lower or "transport" in name_lower:
            vendor = "Uber India Technologies Pvt Ltd"
            inv_no = "UBER-26-89732"
            gstin_v = "27AAFCA3089E1Z4"
            category = "Transport"
            items = [
                ExtractedInvoiceItem(description="Business Travel - Ride Fare", quantity=1.0, unit_price=476.19, amount=476.19, gst_rate=5.0)
            ]
            taxable = 476.19
            cgst = 11.90
            sgst = 11.90
            igst = 0.0
            
        elif "electric" in name_lower or "power" in name_lower or "bescom" in name_lower or "utility" in name_lower:
            vendor = "BSES Yamuna Power Limited"
            inv_no = "BYPL-99234812"
            gstin_v = "07AAFCD0182N1Z8"
            category = "Utilities"
            items = [
                ExtractedInvoiceItem(description="Electricity Charges - May 2026", quantity=1.0, unit_price=4500.0, amount=4500.0, gst_rate=0.0) # Electricity usually exempt
            ]
            taxable = 4500.0
            cgst = 0.0
            sgst = 0.0
            igst = 0.0
            
        elif "rent" in name_lower or "office" in name_lower:
            vendor = "DLF Cyber City Developers"
            inv_no = "DLF-RE-2026-05"
            gstin_v = "06AAACD1294F1Z3"  # Haryana GSTIN
            gstin_r = "07BBBBB2222B2Z2"  # Delhi GSTIN (Inter-state!)
            category = "Rent"
            items = [
                ExtractedInvoiceItem(description="Office Space Rent - Unit 402", quantity=1.0, unit_price=25000.0, amount=25000.0, gst_rate=18.0)
            ]
            taxable = 25000.0
            cgst = 0.0
            sgst = 0.0
            igst = 4500.0  # 18% IGST for Inter-state
            
        else:
            # Generic Vendor
            items = [
                ExtractedInvoiceItem(description="Consulting Service Fee", quantity=1.0, unit_price=847.46, amount=847.46, gst_rate=18.0)
            ]
            taxable = 847.46
            cgst = 76.27
            sgst = 76.27
            igst = 0.0
            
        total = taxable + cgst + sgst + igst
        
        extracted = ExtractedInvoice(
            vendor_name=vendor,
            invoice_date=inv_date,
            invoice_number=inv_no,
            gstin_vendor=gstin_v,
            gstin_recipient=gstin_r,
            taxable_amount=round(taxable, 2),
            cgst=round(cgst, 2),
            sgst_utgst=round(sgst, 2),
            igst=round(igst, 2),
            total_amount=round(total, 2),
            expense_category=category,
            items=items
        )
        
        raw_text = (
            f"MOCK OCR SYSTEM FOR: {filename}\n"
            f"Supplier Name: {vendor}\n"
            f"Invoice Ref: {inv_no}\n"
            f"Date: {inv_date}\n"
            f"Vendor GSTIN: {gstin_v}\n"
            f"Taxable: {taxable}\n"
            f"Taxes: CGST={cgst}, SGST={sgst}, IGST={igst}\n"
            f"Category: {category}\n"
        )
        
        return extracted, raw_text
