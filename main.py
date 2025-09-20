import os
import sqlite3
import re
import googlemaps
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
import google.generativeai as genai
import csv
from io import StringIO, BytesIO
import openpyxl
from openpyxl.styles import Font

DB_PATH = "groundwater.db"

# Load API keys from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set")
if not GOOGLE_MAPS_API_KEY:
    raise ValueError("GOOGLE_MAPS_API_KEY environment variable not set")

# Initialize the Gemini and Google Maps clients
genai.configure(api_key=GEMINI_API_KEY)
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

app = FastAPI(title="Groundwater Info API with Gemini")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def query_db(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_record_by_location(location: str):
    rows = query_db("SELECT * FROM groundwater WHERE lower(location)=lower(?)", (location,))
    return rows[0] if rows else None

# Function to get a general response from the LLM
def get_llm_response(prompt: str):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"LLM API error: {e}")
        return "I am unable to provide a general response at this moment."

class QueryIn(BaseModel):
    message: str
    language: str = "en"

class QueryByLocationIn(BaseModel):
    latitude: float
    longitude: float
    language: str = "en"

# A mapping of common names to the exact names in the database
location_aliases = {
    "salem": "Salem", "salem (extended)": "Salem (Extended)", "puducherry": "Puducherry",
    "kumbakonam": "Kumbakonam Town", "kumbakonam town": "Kumbakonam Town", "kanchipuram": "Kanchipuram",
    "kanchipuram town": "Kanchipuram Town", "karaikal": "Karaikal", "karaikal town": "Karaikal Town",
    "viluppuram": "Viluppuram", "villupuram": "Villupuram"
}

# Translations dictionary (unchanged from your original code)
translations = {
    "en": {
        "greeting": "Hello! I can tell you about groundwater level, quality (pH/TDS/COD/BOD), and irrigation status. Just ask, e.g., 'groundwater level in Kuppam'",
        "no_location": "Please specify a location (example: 'groundwater level in Kuppam')",
        "no_data": "No data found for location: {location}",
        "level_reply": "Groundwater level in {location}: {level} m. Last updated: {date}.",
        "quality_reply": "Water quality in {location}: pH is {ph}, TDS is {tds} mg/L, COD is {cod} mg/L, and BOD is {bod} mg/L. Last updated: {date}.",
        "status_reply": "For {location}, the water is: {status}. Last updated: {date}.",
        "full_report_title": "Here is the full report for {location}:",
        "full_report_level": "• Groundwater Level: {level} m.",
        "full_report_ph": "• pH: {ph}.",
        "full_report_tds": "• TDS: {tds} mg/L.",
        "full_report_cod": "• COD: {cod} mg/L.",
        "full_report_bod": "• BOD: {bod} mg/L.",
        "full_report_status": "• Status: {status}.",
        "full_report_date": "• Last updated: {date}.",
        "unknown_request": "I'm sorry, I don't understand that request. Could you please rephrase?",
        "tds_def": "TDS stands for Total Dissolved Solids. It is a measure of the total concentration of dissolved substances in water, which affects its taste and quality.",
        "bod_def": "BOD stands for Biochemical Oxygen Demand. It measures the amount of oxygen consumed by microorganisms to decompose organic matter in water.",
        "cod_def": "COD stands for Chemical Oxygen Demand. It measures the amount of oxygen required to chemically break down pollutants in water.",
        "ph_def": "pH is a measure of how acidic or alkaline (basic) the water is. A pH of 7 is neutral, while lower values are acidic and higher values are alkaline.",
        "def_error": "I can define TDS, BOD, COD, or pH for you. Please ask for a specific term."
    },
    "ta": {
        "greeting": "வணக்கம்! நிலத்தடி நீர் மட்டம், தரம் (pH/TDS/COD/BOD) மற்றும் பாசன நிலை குறித்து நான் உங்களுக்குச் சொல்ல முடியும். உதாரணமாக, 'குப்பம் நிலத்தடி நீர் மட்டம்' என்று கேளுங்கள்.",
        "no_location": "தயவுசெய்து ஒரு இடத்தைக் குறிப்பிடவும் (உதாரணமாக: 'குப்பம் நிலத்தடி நீர் மட்டம்')",
        "no_data": "{location} இடத்திற்கான தரவு கிடைக்கவில்லை",
        "level_reply": "{location} இல் நிலத்தடி நீர் மட்டம்: {level} மீ. கடைசியாக புதுப்பிக்கப்பட்டது: {date}.",
        "quality_reply": "{location} இல் நீர் தரம்: pH {ph}, TDS {tds} மி.கி/லி, COD {cod} மி.கி/லி, மற்றும் BOD {bod} மி.கி/லி. கடைசியாக புதுப்பிக்கப்பட்டது: {date}.",
        "status_reply": "{location} இல் உள்ள நீர்: {status}. கடைசியாக புதுப்பிக்கப்பட்டது: {date}.",
        "full_report_title": "{location} குறித்த முழு அறிக்கை இங்கே உள்ளது:",
        "full_report_level": "• நிலத்தடி நீர் மட்டம்: {level} மீ.",
        "full_report_ph": "• pH: {ph}.",
        "full_report_tds": "• TDS: {tds} மி.கி/லி.",
        "full_report_cod": "• COD: {cod} மி.கி/லி.",
        "full_report_bod": "• BOD: {bod} மி.கி/லி.",
        "full_report_status": "• நிலை: {status}.",
        "full_report_date": "• கடைசியாக புதுப்பிக்கப்பட்டது: {date}.",
        "unknown_request": "மன்னிக்கவும், அந்த கோரிக்கை எனக்குப் புரியவில்லை. தயவுசெய்து மீண்டும் கேட்க முடியுமா?",
        "tds_def": "TDS என்பது நீரில் கரைந்துள்ள மொத்த திடப்பொருட்களைக் குறிக்கிறது. இது நீரின் சுவை மற்றும் தரத்தை பாதிக்கும் நீரில் கரைந்துள்ள பொருட்களின் மொத்த செறிவின் அளவீடு ஆகும்.",
        "bod_def": "BOD என்பது உயிரி இரசாயன ஆக்ஸிஜன் தேவையைக் குறிக்கிறது. இது நீரில் உள்ள கரிமப் பொருட்களை சிதைக்க நுண்ணுயிரிகளால் பயன்படுத்தப்படும் ஆக்ஸிஜன் அளவை அளவிடுகிறது.",
        "cod_def": "COD என்பது இரசாயன ஆக்ஸிஜன் தேவையைக் குறிக்கிறது. இது நீரில் உள்ள மாசுக்களை இரசாயன ரீதியாக உடைக்கத் தேவையான ஆக்ஸிஜன் அளவை அளவிடுகிறது.",
        "ph_def": "pH என்பது நீர் எவ்வளவு அமிலத்தன்மை கொண்டது அல்லது காரத்தன்மை கொண்டது என்பதற்கான அளவீடு ஆகும். pH 7 என்பது நடுநிலை, அதேசமயம் குறைந்த மதிப்புகள் அமிலத்தன்மை கொண்டவை மற்றும் அதிக மதிப்புகள் காரத்தன்மை கொண்டவை.",
        "def_error": "நான் உங்களுக்கு TDS, BOD, COD அல்லது pH-ஐ வரையறுக்க முடியும். தயவுசெய்து ஒரு குறிப்பிட்ட பதத்தைக் கேளுங்கள்."
    },
    "te": {
        "greeting": "నమస్కారం! నేను మీకు భూగర్భ జలాల స్థాయి, నాణ్యత (pH/TDS/COD/BOD), మరియు సాగునీటి స్థితి గురించి చెప్పగలను. ఉదాహరణకు, 'కుప్పం భూగర్భ జలాల స్థాయి' అని అడగండి.",
        "no_location": "దయచేసి ఒక స్థానాన్ని పేర్కొనండి (ఉదాహరణకు: 'కుప్పం భూగర్భ జలాల స్థాయి')",
        "no_data": "{location} స్థానానికి డేటా కనుగొనబడలేదు",
        "level_reply": "{location} లో భూగర్భ జలాల స్థాయి: {level} మీ. చివరిగా నవీకరించబడింది: {date}.",
        "quality_reply": "{location} లో నీటి నాణ్యత: pH {ph}, TDS {tds} mg/L, COD {cod} mg/L, మరియు BOD {bod} mg/L. చివరిగా నవీకరించబడింది: {date}.",
        "status_reply": "{location} కోసం, నీరు: {status}. చివరిగా నవీకరించబడింది: {date}.",
        "full_report_title": "{location} కోసం పూర్తి నివేదిక ఇక్కడ ఉంది:",
        "full_report_level": "• భూగర్భ జలాల స్థాయి: {level} మీ.",
        "full_report_ph": "• pH: {ph}.",
        "full_report_tds": "• TDS: {tds} mg/L.",
        "full_report_cod": "• COD: {cod} mg/L.",
        "full_report_bod": "• BOD: {bod} mg/L.",
        "full_report_status": "• స్థితి: {status}.",
        "full_report_date": "• చివరిగా నవీకరించబడింది: {date}.",
        "unknown_request": "క్షమించండి, ఆ అభ్యర్థన నాకు అర్థం కాలేదు. దయచేసి తిరిగి అడగగలరా?",
        "tds_def": "TDS అంటే మొత్తం కరిగిన ఘనపదార్థాలు. ఇది నీటి రుచి మరియు నాణ్యతను ప్రభావితం చేసే నీటిలో కరిగిన పదార్ధాల మొత్తం సాంద్రత యొక్క కొలత.",
        "bod_def": "BOD అంటే జీవరసాయన ఆక్సిజన్ డిమాండ్. ఇది నీటిలో సేంద్రీయ పదార్థాన్ని కుళ్ళిపోయేలా సూక్ష్మజీవుల ద్వారా వినియోగించబడే ఆక్సిజన్ మొత్తాన్ని కొలుస్తుంది.",
        "cod_def": "COD అంటే రసాయన ఆక్సిజన్ డిమాండ్. ఇది నీటిలో కాలుష్య కారకాలను రసాయనికంగా విచ్ఛిన్నం చేయడానికి అవసరమైన ఆక్సిజన్ మొత్తాన్ని కొలుస్తుంది.",
        "ph_def": "pH అనేది నీరు ఎంత ఆమ్లంగా లేదా క్షారంగా (బేసిక్) ఉందో కొలిచే కొలత. pH 7 అనేది நடுநிலை, అదేసమయం குறைந்த மதிப்புகள் ఆమ్లంగా మరియు అధిక విలువలు క్షారంగా ఉంటాయి.",
        "def_error": "నేను మీకు TDS, BOD, COD లేదా pH ను నిర్వచించగలను. தயவுசெய்து ఒక నిర్దిஷ்ட పదం కోసం అడగండి."
    }
}


def generate_reply(rec: dict, language: str, query_type: str = "full"):
    """
    Generates a localized and formatted reply based on the record and query type.
    """
    if query_type == "level":
        return translations[language]["level_reply"].format(location=rec['location'], level=rec['groundwater_level'], date=rec['last_updated'])
    if query_type == "quality":
        return translations[language]["quality_reply"].format(location=rec['location'], ph=rec['pH'], tds=rec['TDS'], cod=rec['COD'], bod=rec['BOD'], date=rec['last_updated'])
    if query_type == "status":
        return translations[language]["status_reply"].format(location=rec['location'], status=rec['status'], date=rec['last_updated'])
    
    # Default to full report if no specific type is requested
    return (
        f"{translations[language]['full_report_title'].format(location=rec['location'])}\n"
        f"{translations[language]['full_report_level'].format(level=rec['groundwater_level'])}\n"
        f"{translations[language]['full_report_ph'].format(ph=rec['pH'])}\n"
        f"{translations[language]['full_report_tds'].format(tds=rec['TDS'])}\n"
        f"{translations[language]['full_report_cod'].format(cod=rec['COD'])}\n"
        f"{translations[language]['full_report_bod'].format(bod=rec['BOD'])}\n"
        f"{translations[language]['full_report_status'].format(status=rec['status'])}\n"
        f"{translations[language]['full_report_date'].format(date=rec['last_updated'])}"
    )

def find_location_from_coords(latitude: float, longitude: float):
    """
    Performs reverse geocoding to find a location that matches our database aliases.
    """
    try:
        reverse_geocode_result = gmaps.reverse_geocode((latitude, longitude))
        if not reverse_geocode_result:
            return None

        # Check for matching location aliases in the geocoding results
        for component in reverse_geocode_result:
            for alias, db_location in location_aliases.items():
                # Check if the alias exists in the address components
                if alias.lower() in str(component['address_components']).lower():
                    print(f"Match found: {db_location}")
                    return db_location
        return None
    except Exception as e:
        print(f"Geocoding API error: {e}")
        return None

@app.post("/api/query")
async def handle_query(query_in: QueryIn):
    msg = query_in.message.lower().strip()
    language = query_in.language if query_in.language in translations else "en"
    
    # --- Step 1: Check for keyword-based replies first ---
    if any(k in msg for k in ["hi", "hello", "hey"]):
        return {"reply": translations[language]["greeting"]}
    if any(k in msg for k in ["what is", "define", "meaning of", "what does"]):
        if "tds" in msg: return {"reply": translations[language]["tds_def"]}
        if "bod" in msg: return {"reply": translations[language]["bod_def"]}
        if "cod" in msg: return {"reply": translations[language]["cod_def"]}
        if "ph" in msg: return {"reply": translations[language]["ph_def"]}
        return {"reply": translations[language]["def_error"]}

    # --- Step 2: Query the local database for specific data ---
    location = None
    for alias, db_location in location_aliases.items():
        if alias in msg:
            location = db_location
            break

    if location:
        rec = get_record_by_location(location)
        if not rec:
            return {"reply": translations[language]["no_data"].format(location=location)}
            
        query_type = "full"
        if any(k in msg for k in ["level", "water table"]):
            query_type = "level"
        elif any(k in msg for k in ["ph", "tds", "cod", "bod", "quality"]):
            query_type = "quality"
        elif any(k in msg for k in ["status", "irrigation", "drinking", "recommended"]):
            query_type = "status"

        return {"reply": generate_reply(rec, language, query_type), "location": rec['location']}
    
    # --- Step 3: If no data-specific query is detected, send to LLM ---
    llm_prompt = f"The user is asking a question in English. The reply must be in {language} and conversational.\nUser query: {msg}"
    llm_response = get_llm_response(llm_prompt)
    
    return {"reply": llm_response}

# --- NEW ENDPOINT FOR LOCATION-BASED QUERIES ---
@app.post("/api/query_by_location")
async def handle_location_query(query_in: QueryByLocationIn):
    language = query_in.language if query_in.language in translations else "en"
    
    # Find the location name from the provided latitude and longitude
    location_name = find_location_from_coords(query_in.latitude, query_in.longitude)
    
    if location_name:
        # Get the groundwater record for the detected location
        rec = get_record_by_location(location_name)
        
        if rec:
            # Generate the full report and return it
            reply = generate_reply(rec, language, "full")
            return {"reply": reply, "location": rec['location']}
        else:
            # If no data found for the location, return a specific message
            return {"reply": translations[language]["no_data"].format(location=location_name)}
    
    # If no matching location could be found, return a generic message
    return {"reply": translations[language]["unknown_request"]}

# --- NEW ENDPOINT TO GENERATE AND DOWNLOAD EXCEL REPORT ---
@app.get("/api/report/{location}")
async def get_report(location: str):
    rec = get_record_by_location(location)
    if not rec:
        raise HTTPException(status_code=404, detail="Location not found")

    output = BytesIO()
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = f"Groundwater Report for {location}"

    # Set a header for the report
    title_cell = sheet['A1']
    title_cell.value = "Groundwater Report"
    title_cell.font = Font(size=16, bold=True)
    
    # Add a blank row for spacing
    sheet.append([])

    # Write data in a structured key-value format
    data = [
        ("Location", rec['location']),
        ("Last Updated", rec['last_updated']),
        ("Groundwater Level", f"{rec['groundwater_level']} m"),
        ("pH", rec['pH']),
        ("TDS", f"{rec['TDS']} mg/L"),
        ("COD", f"{rec['COD']} mg/L"),
        ("BOD", f"{rec['BOD']} mg/L"),
        ("Status", rec['status'])
    ]

    for row in data:
        sheet.append(row)

    # Save the workbook to the in-memory buffer
    workbook.save(output)
    output.seek(0)

    return Response(
        content=output.read(),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': f'attachment; filename=groundwater_report_{location}.xlsx'
        }
    )