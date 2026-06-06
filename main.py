import os
import shutil
from datetime import datetime, date
from typing import List, Optional
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel

# Import local modules
from database import init_db, get_db, Invoice, InvoiceItem, ChatHistory
from schemas import (
    InvoiceResponse, InvoiceUpdate, ChatMessageResponse, 
    SettingsResponse, SettingsUpdate
)
from extractor import InvoiceExtractor
from assistant import AIAssistant

# Create uploads directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize DB on start
init_db()

app = FastAPI(title="AI Invoice & GST Assistant API")

# Add CORS Middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper to read/write settings in .env
def get_env_setting(key: str) -> str:
    return os.environ.get(key, "")

def update_env_file(gemini_key: Optional[str] = None, openai_key: Optional[str] = None, business_gstin: Optional[str] = None):
    env_vars = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    parts = line.strip().split("=", 1)
                    if len(parts) == 2:
                        env_vars[parts[0].strip()] = parts[1].strip()
                        
    if gemini_key is not None:
        env_vars["GEMINI_API_KEY"] = gemini_key
        os.environ["GEMINI_API_KEY"] = gemini_key
    if openai_key is not None:
        env_vars["OPENAI_API_KEY"] = openai_key
        os.environ["OPENAI_API_KEY"] = openai_key
    if business_gstin is not None:
        env_vars["BUSINESS_GSTIN"] = business_gstin
        os.environ["BUSINESS_GSTIN"] = business_gstin
        
    with open(".env", "w") as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")

# --- Settings Endpoints ---
@app.get("/api/settings", response_model=SettingsResponse)
def get_settings():
    db_url = os.environ.get("DATABASE_URL", "sqlite:///./invoice_assistant.db")
    # Mask key for response
    g_configured = bool(os.environ.get("GEMINI_API_KEY"))
    o_configured = bool(os.environ.get("OPENAI_API_KEY"))
    gstin = os.environ.get("BUSINESS_GSTIN", "")
    
    return SettingsResponse(
        database_url=db_url,
        gemini_api_key_configured=g_configured,
        openai_api_key_configured=o_configured,
        business_gstin=gstin
    )

@app.post("/api/settings", response_model=SettingsResponse)
def update_settings(settings: SettingsUpdate):
    update_env_file(
        gemini_key=settings.gemini_api_key,
        openai_key=settings.openai_api_key,
        business_gstin=settings.business_gstin
    )
    return get_settings()


# --- Invoice Endpoints ---

@app.post("/api/invoices/upload", response_model=InvoiceResponse)
async def upload_invoice(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    # Validate extension
    if not InvoiceExtractor.get_supported_extension(file.filename):
        raise HTTPException(
            status_code=400, 
            detail="Unsupported file format. Please upload PDF, PNG, JPG, or WEBP."
        )
        
    # Save file
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Read bytes for extractor
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    # Pre-create entry in DB as pending
    db_invoice = Invoice(
        file_name=file.filename,
        file_path=file_path,
        status="processing",
        total_amount=0.0
    )
    db.add(db_invoice)
    db.commit()
    db.refresh(db_invoice)

    try:
        # Extract invoice metadata
        extracted_data, raw_ocr = InvoiceExtractor.extract_invoice_data(
            file_bytes=file_bytes,
            filename=file.filename
        )
        
        # Parse date if available
        parsed_date = None
        if extracted_data.invoice_date:
            try:
                parsed_date = datetime.strptime(extracted_data.invoice_date, "%Y-%m-%d").date()
            except ValueError:
                pass
                
        # Update invoice table
        db_invoice.vendor_name = extracted_data.vendor_name
        db_invoice.invoice_date = parsed_date
        db_invoice.invoice_number = extracted_data.invoice_number
        db_invoice.gstin_vendor = extracted_data.gstin_vendor
        db_invoice.gstin_recipient = extracted_data.gstin_recipient
        db_invoice.taxable_amount = extracted_data.taxable_amount
        db_invoice.cgst = extracted_data.cgst
        db_invoice.sgst_utgst = extracted_data.sgst_utgst
        db_invoice.igst = extracted_data.igst
        db_invoice.total_amount = extracted_data.total_amount
        db_invoice.expense_category = extracted_data.expense_category
        db_invoice.status = "processed"
        db_invoice.raw_ocr_text = raw_ocr
        
        # Add line items
        if extracted_data.items:
            for item in extracted_data.items:
                db_item = InvoiceItem(
                    invoice_id=db_invoice.id,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    amount=item.amount,
                    gst_rate=item.gst_rate
                )
                db.add(db_item)
                
        db.commit()
        db.refresh(db_invoice)
        
    except Exception as e:
        db_invoice.status = "failed"
        db_invoice.raw_ocr_text = f"Extraction failed with error: {str(e)}"
        db.commit()
        print(f"Error extracting invoice: {e}")
        # Return what we can or raise error
        
    return db_invoice

@app.get("/api/invoices", response_model=List[InvoiceResponse])
def get_invoices(
    category: Optional[str] = None,
    vendor: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Invoice)
    
    if category:
        query = query.filter(Invoice.expense_category == category)
    if vendor:
        query = query.filter(Invoice.vendor_name.ilike(f"%{vendor}%"))
        
    if start_date:
        try:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(Invoice.invoice_date >= s_dt)
        except ValueError:
            pass
            
    if end_date:
        try:
            e_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(Invoice.invoice_date <= e_dt)
        except ValueError:
            pass
            
    return query.order_by(Invoice.id.desc()).all()

@app.get("/api/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoice

@app.put("/api/invoices/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: int, 
    updated_data: InvoiceUpdate, 
    db: Session = Depends(get_db)
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
        
    # Apply changes
    for key, value in updated_data.model_dump(exclude_unset=True).items():
        setattr(invoice, key, value)
        
    db.commit()
    db.refresh(invoice)
    return invoice

@app.delete("/api/invoices/{invoice_id}")
def delete_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
        
    # Remove file from storage
    if os.path.exists(invoice.file_path):
        try:
            os.remove(invoice.file_path)
        except OSError:
            pass
            
    db.delete(invoice)
    db.commit()
    return {"detail": "Invoice successfully deleted"}


# --- GST Reports Endpoint ---

@app.get("/api/gst-report")
def get_gst_report(
    year: int, 
    month: Optional[int] = None, 
    db: Session = Depends(get_db)
):
    """
    Generates a structured GST report (CGST, SGST, IGST aggregates + categories breakdown).
    """
    query = db.query(Invoice).filter(Invoice.status == "processed")
    
    # Date filtration
    if month:
        # Start and end date for month
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        start_d = date(year, month, 1)
        end_d = date(year, month, last_day)
        query = query.filter(Invoice.invoice_date >= start_d, Invoice.invoice_date <= end_d)
    else:
        # Whole year
        start_d = date(year, 1, 1)
        end_d = date(year, 12, 31)
        query = query.filter(Invoice.invoice_date >= start_d, Invoice.invoice_date <= end_d)
        
    invoices = query.all()
    
    # Calculation
    total_taxable = sum(i.taxable_amount for i in invoices)
    total_cgst = sum(i.cgst for i in invoices)
    total_sgst = sum(i.sgst_utgst for i in invoices)
    total_igst = sum(i.igst for i in invoices)
    total_gross = sum(i.total_amount for i in invoices)
    total_gst = total_cgst + total_sgst + total_igst
    
    # Category splits
    categories = {}
    for i in invoices:
        cat = i.expense_category
        categories[cat] = categories.get(cat, 0.0) + i.total_amount
        
    return {
        "summary": {
            "period": f"{year}-{month:02d}" if month else f"{year}",
            "invoice_count": len(invoices),
            "taxable_amount": round(total_taxable, 2),
            "cgst": round(total_cgst, 2),
            "sgst_utgst": round(total_sgst, 2),
            "igst": round(total_igst, 2),
            "total_gst": round(total_gst, 2),
            "total_gross_spend": round(total_gross, 2)
        },
        "category_breakdown": {k: round(v, 2) for k, v in categories.items()},
        "invoices": [
            {
                "id": i.id,
                "vendor_name": i.vendor_name,
                "invoice_number": i.invoice_number,
                "invoice_date": i.invoice_date.strftime("%Y-%m-%d") if i.invoice_date else None,
                "taxable_amount": i.taxable_amount,
                "cgst": i.cgst,
                "sgst_utgst": i.sgst_utgst,
                "igst": i.igst,
                "total_amount": i.total_amount,
                "gstin_vendor": i.gstin_vendor
            }
            for i in invoices
        ]
    }


# --- Assistant Chat Endpoints ---

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat", response_model=ChatMessageResponse)
def post_chat_message(request: ChatRequest, db: Session = Depends(get_db)):
    # Save user message to database
    user_msg = ChatHistory(role="user", content=request.message)
    db.add(user_msg)
    db.commit()
    
    # Fetch AI response
    response_text = AIAssistant.get_response(
        user_message=request.message,
        db=db
    )
    
    # Save bot response to database
    bot_msg = ChatHistory(role="assistant", content=response_text)
    db.add(bot_msg)
    db.commit()
    db.refresh(bot_msg)
    
    return bot_msg

@app.get("/api/chat/history", response_model=List[ChatMessageResponse])
def get_chat_history(db: Session = Depends(get_db)):
    # Limit to last 50 messages to keep UI light
    return db.query(ChatHistory).order_by(ChatHistory.id.asc()).limit(50).all()

@app.post("/api/chat/clear")
def clear_chat_history(db: Session = Depends(get_db)):
    db.query(ChatHistory).delete()
    db.commit()
    return {"detail": "Chat history cleared"}


# Serve static directory for single page application (SPA)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
