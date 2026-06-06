import sys
import os

# Force UTF-8 encoding for stdout and stderr to handle emojis on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Set current path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    print("==================================================")
    print("Starting AI Invoice & GST Assistant Verification...")
    print("==================================================")

    # 1. Database Initialization
    print("\n[Step 1] Initializing Database Schema...")
    try:
        from database import init_db, SessionLocal, Invoice, InvoiceItem
        init_db()
        print("[SUCCESS] Database schema created successfully.")
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        sys.exit(1)

    # 2. Database Read/Write test
    print("\n[Step 2] Testing Database CRUD operations...")
    db = SessionLocal()
    try:
        # Create a test invoice
        test_invoice = Invoice(
            file_name="test_bill.png",
            file_path="uploads/test_bill.png",
            vendor_name="Test Vendor Corp",
            invoice_number="TX-9999",
            taxable_amount=100.0,
            cgst=9.0,
            sgst_utgst=9.0,
            total_amount=118.0,
            expense_category="Office Supplies",
            status="processed"
        )
        db.add(test_invoice)
        db.commit()
        db.refresh(test_invoice)
        
        # Add a line item
        test_item = InvoiceItem(
            invoice_id=test_invoice.id,
            description="Premium Black Pens",
            quantity=10.0,
            unit_price=10.0,
            amount=100.0,
            gst_rate=18.0
        )
        db.add(test_item)
        db.commit()
        
        # Query it back
        queried = db.query(Invoice).filter(Invoice.id == test_invoice.id).first()
        assert queried is not None
        assert len(queried.items) == 1
        assert queried.items[0].description == "Premium Black Pens"
        print(f"[SUCCESS] Database read/write check passed. Test invoice created with ID {queried.id}.")
        
        # Cleanup
        db.delete(queried)
        db.commit()
        print("[SUCCESS] Database cleanup completed.")
    except Exception as e:
        print(f"[ERROR] Database CRUD test failed: {e}")
        db.close()
        sys.exit(1)
    finally:
        db.close()

    # 3. Test Mock OCR Extractor
    print("\n[Step 3] Testing OCR Extractor in Mock Mode...")
    try:
        from extractor import InvoiceExtractor
        extracted, raw_text = InvoiceExtractor.extract_invoice_data(
            file_bytes=b"", 
            filename="uber_ride_receipt.png"
        )
        print(f"[SUCCESS] Extracted Vendor: {extracted.vendor_name}")
        print(f"[SUCCESS] Extracted Category: {extracted.expense_category}")
        print(f"[SUCCESS] Extracted Taxable Amount: Rs {extracted.taxable_amount}")
        print(f"[SUCCESS] Extracted Total Amount: Rs {extracted.total_amount}")
        assert extracted.expense_category == "Transport"
        print("[SUCCESS] OCR Mock extraction test passed.")
    except Exception as e:
        print(f"[ERROR] OCR Mock extraction failed: {e}")
        sys.exit(1)

    # 4. Test Assistant Mock Q&A
    print("\n[Step 4] Testing AI Assistant in Mock Mode...")
    try:
        from assistant import AIAssistant
        from database import SessionLocal
        
        # Re-add temporary record for assistant to find
        db = SessionLocal()
        temp_inv = Invoice(
            file_name="reliance_digital.png",
            file_path="uploads/reliance_digital.png",
            vendor_name="Reliance Retail Limited",
            invoice_number="RRL-123",
            taxable_amount=1000.0,
            cgst=90.0,
            sgst_utgst=90.0,
            total_amount=1180.0,
            expense_category="Inventory",
            status="processed"
        )
        db.add(temp_inv)
        db.commit()
        
        # Test chat query
        ans1 = AIAssistant.get_response("How much did I spend on Inventory?", db)
        print(f"[SUCCESS] Chat query 'Inventory spend':\n---\n{ans1}\n---")
        assert "reliance" in ans1.lower() or "inventory" in ans1.lower()
        
        ans2 = AIAssistant.get_response("Show me my GST details", db)
        print(f"[SUCCESS] Chat query 'GST details':\n---\n{ans2}\n---")
        assert "gst" in ans2.lower()
        
        # Cleanup
        db.delete(temp_inv)
        db.commit()
        db.close()
        print("[SUCCESS] AI Assistant mock Q&A test passed.")
    except Exception as e:
        print(f"[ERROR] AI Assistant test failed: {e}")
        if 'db' in locals():
            db.close()
        sys.exit(1)

    # 5. Test FastAPI Client Endpoints
    print("\n[Step 5] Testing FastAPI App Endpoints...")
    try:
        from fastapi.testclient import TestClient
        from main import app
        
        client = TestClient(app)
        
        # Test /api/settings GET
        res_set = client.get("/api/settings")
        assert res_set.status_code == 200
        settings_data = res_set.json()
        print(f"[SUCCESS] Endpoint GET /api/settings verified. Configured: Gemini={settings_data['gemini_api_key_configured']}")

        # Test /api/invoices GET
        res_inv = client.get("/api/invoices")
        assert res_inv.status_code == 200
        print("[SUCCESS] Endpoint GET /api/invoices verified.")

        # Test /api/gst-report GET
        res_rep = client.get("/api/gst-report?year=2026")
        assert res_rep.status_code == 200
        report_data = res_rep.json()
        assert "summary" in report_data
        print("[SUCCESS] Endpoint GET /api/gst-report verified.")

        # Test /api/chat POST
        res_chat = client.post("/api/chat", json={"message": "hello"})
        assert res_chat.status_code == 200
        chat_data = res_chat.json()
        assert chat_data["role"] == "assistant"
        print(f"[SUCCESS] Endpoint POST /api/chat verified. Response: '{chat_data['content'][:50]}...'")

        print("\n[SUCCESS] FastAPI Client checks completed successfully!")
    except Exception as e:
        print(f"[ERROR] FastAPI App testing failed: {e}")
        sys.exit(1)

    print("\n==================================================")
    print("All backend verification steps passed successfully!")
    print("==================================================")

if __name__ == "__main__":
    main()
