from typing import Text
import streamlit as st
import easyocr
import re
from PIL import Image
import io
import sqlite3
import json

#Project to extract data from an uploaded image of a business card with the details specified
#Using OCR to recognixe the image and extract info
#Sqllite for database connection
#Using streamlit for the user interface



def extract_info(ocr_results):
    """
    Process the OCR results to extract specific information using direct ocr results.
    """
    
    # Initialize results
    emails = []
    phones = []
    websites = []
    address_lines = []
    aggregated_text = ' '.join([item[1] for item in ocr_results])

    website_pattern = r"[wW]{3}\s?[a-zA-Z0-9.-]+com"
    websites = re.findall(website_pattern, aggregated_text)

    # Extract directly from OCR results
    for idx, item in enumerate(ocr_results):
        text = item[1]
        # Extract emails
        if "@" in text and "." in text:  # Simple heuristic
            emails.append(text)

        # Extract phone numbers
        if re.match(r"(\+?\d{1,3}[-\.\s]?(\d{1,4}[-\.\s]?){2,3}\d{1,4})", text) and len(re.sub(r'\D', '', text)) > 7:
            phones.append(text)

        # Check for address lines
        if text.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")) and ( text.endswith(",") or text.endswith(";")):
            address_lines.append(text)
           
        if re.search(r"\d{6,7}$", text):  
            address_lines.append(text)# Check if next line ends with pincode
                

    address = ' '.join(address_lines)

    # Extract company name
    non_company_texts = [item[1] for item in ocr_results[:2]] + emails + phones + websites + address_lines
    company_texts = [item[1] for item in ocr_results if item[1] not in non_company_texts]
    company_name = ' '.join(company_texts)

    # Using the provided rules for name and designation
    name = ocr_results[0][1] if ocr_results else None
    designation = ocr_results[1][1] if len(ocr_results) > 1 else None

    return {
        "Card Holder Name": name,
        "Designation": designation,
        "Company Name": company_name,
        "Address": address,
        "Emails": emails,
        "Phones": phones,
        "Websites": websites
    }


# Initialize Database
def initialize_db():
    conn = sqlite3.connect('business_cards.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS cards
                 (id INTEGER PRIMARY KEY,
                  company_name TEXT, 
                  card_holder_name TEXT, 
                  designation TEXT, 
                  mobile_numbers TEXT,
                  email_addresses TEXT,
                  website_url TEXT, 
                  area TEXT, 
                  city TEXT, 
                  state TEXT, 
                  pin_code TEXT, 
                  image BLOB)''')
    conn.commit()
    conn.close()

# Insert Data into Database
def insert_data(extracted_info, image_data):
    conn = sqlite3.connect('business_cards.db')
    cursor = conn.cursor()

    # Data processing for the insert
    emails = ', '.join(extracted_info["Emails"]) if extracted_info["Emails"] else None
    phones = ', '.join(extracted_info["Phones"]) if extracted_info["Phones"] else None
    websites = ', '.join(extracted_info["Websites"]) if extracted_info["Websites"] else None

    # The table structure is:
    # (id, company_name, card_holder_name, designation, mobile_numbers, 
    #  email_addresses, website_url, area, city, state, pin_code, image)
    # Inserting the full address into the 'area' column for this example.
    data = (extracted_info["Company Name"], extracted_info["Card Holder Name"], 
            extracted_info["Designation"], phones, emails, websites, 
            extracted_info["Address"], None, None, None, image_data)

    cursor.execute("INSERT INTO cards (company_name, card_holder_name, designation, mobile_numbers, email_addresses, website_url, area, city, state, pin_code, image) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", data)

    conn.commit()
    conn.close()




# Fetch All Data from Database
def fetch_all_data():
    conn = sqlite3.connect('business_cards.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cards")
    records = cursor.fetchall()
    conn.close()
    return records

# Update Data in Database
def update_data(card_id, new_data):
    conn = sqlite3.connect('business_cards.db')
    cursor = conn.cursor()
    
    cursor.execute('''UPDATE cards 
                      SET company_name=?, card_holder_name=?, designation=?, mobile_numbers=?, email_addresses=?, website_url=?, area=?, city=?, state=?, pin_code=?
                      WHERE id=?''', (new_data['company_name'], new_data['card_holder_name'], new_data['designation'], 
                                       json.dumps(new_data['mobile_numbers']), json.dumps(new_data['email_addresses']), new_data['website_url'], 
                                       new_data['area'], new_data['city'], new_data['state'], new_data['pin_code'], card_id))
    
    conn.commit()
    conn.close()

# Delete Data from Database
def delete_data(card_id):
    conn = sqlite3.connect('business_cards.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cards WHERE id=?", (card_id,))
    conn.commit()
    conn.close()

# Streamlit Interface
st.title("Business Card Information Extractor")

# CSS for background
st.markdown("""
    <style>
        body {
            background-color: #ADD8E6;
        }
    </style>
    """, unsafe_allow_html=True)

# Sidebar and navigation
menu = st.sidebar.selectbox("Choose an action", ["Upload & Extract", "View All", "Update", "Delete"])

if menu == "Upload & Extract":
    uploaded_file = st.file_uploader("Choose a business card image...", type=["jpg", "png", "jpeg"])

    if uploaded_file:
        # Convert the uploaded file buffer to bytes
        image = Image.open(uploaded_file)
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')

        # OCR processing
        reader = easyocr.Reader(['en'])
        result = reader.readtext(img_byte_arr.getvalue())

        # Extract info and display
        extracted_info = extract_info(result)
        st.markdown("### Extracted details : ")
        for key, value in extracted_info.items():
            if isinstance(value, list) and key in ["Phones", "Emails"]:
                for v in value:
                    st.write(f"{key[:-1]}: {v}")
            else:
                st.write(f"{key}: {value}")

        # Button to save extracted info to the database
        if st.button("Save to Database"):
            insert_data(extracted_info, img_byte_arr.getvalue())
            st.success("Data saved to database!")

elif menu == "View All":
    st.header("Stored Business Card Data")
    records = fetch_all_data()

    for record in records:
        st.write("ID:", record[0])
        
        if record[1]:
            st.write("Company Name:", record[1])
        if record[2]:
            st.write("Card Holder Name:", record[2])
        if record[3]:
            st.write("Designation:", record[3])
        
        mobiles = record[4].split(",") if record[4] else []
        for mobile in mobiles:
            st.write("Mobile:", mobile)
        
        emails = record[5].split(",") if record[5] else []
        for email in emails:
            st.write("Email:", email)
        
        if record[6]:
            st.write("Website URL:", record[6])
        if record[7]:
            st.write("Area:", record[7])
        if record[8]:
            st.write("City:", record[8])
        if record[9]:
            st.write("State:", record[9])
        if record[10]:
            st.write("Pin Code:", record[10])
        
        st.write("------")

elif menu == "Update":
    st.header("Update Data")
    st.write("Enter the ID of the card you want to update:")
    card_id = st.number_input("Card ID", min_value=1)

    # Form for new data
    new_data = {
        'company_name': st.text_input("Company Name"),
        'card_holder_name': st.text_input("Card Holder Name"),
        'designation': st.text_input("Designation"),
        'mobile_numbers': st.text_input("Mobile Numbers (comma-separated)"),
        'email_addresses': st.text_input("Email Addresses (comma-separated)"),
        'website_url': st.text_input("Website URL"),
        'area': st.text_input("Area"),
        'city': st.text_input("City"),
        'state': st.text_input("State"),
        'pin_code': st.text_input("Pin Code")
    }
    # The button to execute the update
    if st.button("Submit Update"):
        update_data(card_id, new_data)
        st.success("Data updated successfully!")

elif menu == "Delete":
    st.header("Delete Data")
    st.write("Enter the ID of the card you want to delete:")
    card_id = st.number_input("Card ID", min_value=1)
    # Implement logic for deleting data
    delete_data(card_id)
    st.success("Data deleted successfully!")

initialize_db()


