AI Invoice & GST Assistant for Small Businesses
A fully featured, visually stunning web application that helps small Indian businesses digitize physical invoices, automatically extract GST data, categorize expenses, generate GST returns summaries (like GSTR-3B helpers), and query their financial records using an interactive AI assistant.

User Review Required
IMPORTANT

Database Selection:

PostgreSQL is not installed locally on this environment.
To ensure the application runs instantly with zero manual setup, we will use SQLite as the default database.
We will structure the database using SQLAlchemy so that transitioning to PostgreSQL is as simple as updating the DATABASE_URL in the .env file.
AI OCR & Extraction API Keys:

Because Tesseract OCR is not installed locally, standard local OCR would be fragile or require heavy installation steps.
We propose using a Multimodal LLM approach (via Google Gemini API or OpenAI API). This sends the invoice image/PDF directly to the LLM, extracting structured JSON details in one pass. It is 100% self-contained and significantly more accurate.
The application will provide a Settings tab directly in the UI where you can paste your Gemini or OpenAI API Key, which will save to .env. If no API Key is provided, the application will run in a Mock Demo Mode so you can still experience the UI and workflows immediately.
Open Questions
NOTE

Do you have a preferred LLM API key already (e.g., Google Gemini or OpenAI) that you would like us to pre-configure, or is the UI input setup sufficient?
For the GST Reports, should we focus on GSTR-3B format details (split by CGST, SGST, IGST, and Input Tax Credit eligibility) or general GST summaries?
Proposed Changes
We will create a self-contained Python FastAPI project in your workspace C:\Users\Krishna\OneDrive\Desktop\Ai - invoice.

HTTP / JSON
Upload Files
Read/Write Records
Chat Queries
Frontend: HTML5, CSS3, JS, Chart.js
FastAPI Backend
AI Multimodal Extractor: Gemini/OpenAI
SQLAlchemy: SQLite / PostgreSQL
AI Assistant Engine
Backend Structure
[NEW] 
main.py
The FastAPI entrypoint. Serves API endpoints and static assets.

Setup route handlers for invoice uploads, editing, reports, chat, and settings.
Enable CORS.
[NEW] 
database.py
SQLAlchemy database configuration, model declarations, and session management.

Models: Invoice, InvoiceItem, ChatHistory.
Supports dynamic connection URL from .env.
[NEW] 
schemas.py
Pydantic schemas for request validation, response serialization, and structured LLM outputs.

Schema definitions for Invoice details (Vendor, GSTIN, Amounts, Category).
[NEW] 
extractor.py
Handles invoice processing.

Multi-modal extractors using google-generativeai and openai.
Automatically normalizes categories (Transport, Inventory, Utilities, Office Supplies, Meals & Entertainment, Others).
Fallback mock data processor if no API keys are present.
[NEW] 
assistant.py
The AI chat Q&A assistant logic.

Converts user questions into SQL-like filters or retrieves invoice context to let the LLM generate clean financial answers.
[NEW] 
config.py
Configuration settings loader utilizing python-dotenv.

Frontend Structure
We will place all frontend code in a static/ directory to serve directly from FastAPI. This enables a zero-compile, zero-dependency, ultra-fast single page application dashboard.

[NEW] 
index.html
The central structure of the single page application.

Dashboard view with stats cards and charts.
Drag-and-drop file upload drawer.
Invoice data grid with status indicators, search, filtering, and manual editor sidebar.
GSTR-3B Summary and monthly reports tab.
Interactive AI Assistant chat interface.
Settings panel.
[NEW] 
styles.css
Custom Vanilla CSS implementation focusing on a premium developer experience.

Color palette: Deep space dark mode (HSL variables) with cyan/purple glowing neon highlights.
Glassmorphic panels with subtle gradients.
Micro-animations for buttons, drag-and-drop hover, and active states.
Fully responsive layout using CSS Flexbox/Grid.
Inter and Outfit Google Fonts for high-end typography.
[NEW] 
app.js
Frontend logic handling:

Multi-view routing (Dashboard, Invoices, GST Reports, AI Chat, Settings).
AJAX API calls for upload, edit, reports, chat, and settings.
Charts instantiation using Chart.js (Spend-by-category, Monthly tax distribution).
File upload visual transitions, drag-over styles, and upload progress triggers.
Project Configuration Files
[NEW] 
.env
Local environment settings including API keys and Database URL.

[NEW] 
requirements.txt
Python package dependencies: fastapi, uvicorn, sqlalchemy, python-dotenv, google-generativeai, openai, python-multipart, pydantic.

Verification Plan
Automated Tests
Create a verification script verify_backend.py to:
Test database connection and schema creation.
Mock upload an invoice and verify schema validation.
Validate mock AI responses.
Manual Verification
Run the FastAPI dev server: uvicorn main:app --reload
Open the dashboard in the browser: http://localhost:8000
Perform verification:
Drag and drop sample invoice files.
Check if the extraction drawer opens, runs, and displays progress.
Modify fields manually in the edit sidebar and save.
Query the AI chat assistant (e.g., "Show me my CGST total").
Generate and download a GST report.
