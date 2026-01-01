import streamlit as st
import gspread
import json
import pytz
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime

# --- සැකසුම් (Setup) ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Google Sheet එකට සම්බන්ධ වීම (Cloud සහ Local දෙකටම වැඩ කරන විදිය)
try:
    if "google_credentials" in st.secrets:
        # මේ කොටස වැඩ කරන්නේ අන්තර්ජාලයේදී (Streamlit Cloud)
        creds_json = json.loads(st.secrets["google_credentials"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    else:
        # මේ කොටස වැඩ කරන්නේ ඔයාගේ මැෂින් එකේදී (Local)
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)

    client = gspread.authorize(creds)

    # ඔයාගේ Sheet එකේ නම මෙතන දාන්න (Link එක දැම්මනම් ඒකම තියන්න)
    # පහත පේළිය ඔයාගේ කලින් code එකේ තිබුන විදියටම තියන්න:
    sheet = client.open("Box_Transfer_Data").sheet1 

except Exception as e:
    st.error(f"Error connecting to Google Sheets: {e}")
    st.stop()
# --- App එකේ පෙනුම ---
st.title("🏭 Warehouse Transfer App")

# Sidebar එක - Sender ද Receiver ද කියලා තෝරන්න
menu = st.sidebar.radio("Choose your task:", ["📦 Send Stock", "📥 Receive Stock"])

# --- යවන කෙනාගේ කොටස (SENDER) ---
if menu == "📦 Send Stock ":
    st.header("Sending new shipments")
    
    with st.form("send_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            sku = st.text_input("SKU Number")
            origin = st.selectbox("The departing warehouse", [ "WH 3"])
            sender_name = st.text_input("Supervisor name")
            
        with col2:
            box_count = st.number_input("Number of boxes", min_value=1, step=1)
            destination = st.selectbox("The warehouse that will be received", ["WH 1", "WH 2", "WH 5","WH VENUS"])
            
       # ලංකාවේ Timezone එක සෙට් කිරීම
            lk_tz = pytz.timezone('Asia/Colombo') 
            

        # දැන් වෙලාව ගන්නේ ලංකාවට අනුව
            current_date = datetime.now(lk_tz).strftime("%Y-%m-%d")
            current_time = datetime.now(lk_tz).strftime("%H:%M:%S")
            submitted = st.form_submit_button("Submit Transfer")
        
        if submitted:
            if not sku or not sender_name:
                st.warning("Please enter SKU and name.")
            else:
                # Unique ID එකක් හදමු (වෙලාව පදනම් කරගෙන)
                transfer_id = int(datetime.now().timestamp())
                
                # Google Sheet එකට දාන Data පේළිය
                # පිළිවෙල: Transfer_ID, SKU, Date, Time, Origin, Dest, Sent_Count, Sender, Status...
                new_row = [
                    transfer_id, 
                    sku, 
                    current_date, 
                    current_time, 
                    origin, 
                    destination, 
                    box_count, 
                    sender_name, 
                    "Sent",  # Status එක Sent ලෙස යනවා
                    "", "", "", "" # Receiver columns හිස්ව තියනවා
                ]
                
                sheet.append_row(new_row)
                st.success(f"Success! Transfer ID: {transfer_id} Included under.")

# --- බාරගන්න කෙනාගේ කොටස (RECEIVER) ---
elif menu == "📥 Receive Stock":
    st.header("Receiving shipments")
    
    # 1. Sheet එකේ Data ඔක්කොම ගන්නවා
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    # 2. Status එක 'Sent' වෙලා තියෙන ඒවා විතරක් පෙන්නන්න
    if not df.empty and 'Status' in df.columns:
        pending_items = df[df['Status'] == 'Sent']
        
        if pending_items.empty:
            st.info("There is currently no new stock to accept.")
        else:
            st.write("Available stocks:")
            # ලිස්ට් එක පෙන්නනවා
            st.dataframe(pending_items[['Transfer_ID', 'SKU', 'Origin_Warehouse', 'Sent_Box_Count', 'Date']])
            
            # බාරගන්න අදාළ ID එක තෝරන්න
            selected_id = st.selectbox("Select the Transfer ID to receive:", pending_items['Transfer_ID'].unique())
            
            st.divider()
            st.subheader("Receive details")
            
            with st.form("receive_form"):
                rec_name = st.text_input("Receiver (Supervisor) නම")
                rec_count = st.number_input("Received Count", min_value=0)
                
                confirm = st.form_submit_button("Confirm Receipt")
                
                if confirm:
                    if not rec_name:
                        st.warning("Please enter your name.")
                    else:
                        # Update කරන්න ඕන පේළිය හොයාගැනීම
                        cell = sheet.find(str(selected_id))
                        row_num = cell.row
                        
                        # දැනට වෙලාව
                        rec_date = datetime.now().strftime("%Y-%m-%d")
                        rec_time = datetime.now().strftime("%H:%M:%S")
                        
                        # Sheet එක Update කිරීම (Column අංක හරියටම බලන්න ඕන Sheet එකේ හැටියට)
                        # මෙතන මම උපකල්පනය කරනවා Status තියෙන්නේ Col 9 කියලා. 
                        # ඔයාගේ Sheet එකේ Column පිළිවෙල අනුව මේ අංක වෙනස් වෙන්න පුළුවන්.
                        
                        sheet.update_cell(row_num, 9, "Received") # Status update
                        sheet.update_cell(row_num, 10, rec_date)  # Received Date
                        sheet.update_cell(row_num, 11, rec_time)  # Received Time
                        sheet.update_cell(row_num, 12, rec_count) # Received Count
                        sheet.update_cell(row_num, 13, rec_name)  # Receiver Name
                        
                        st.success("The goods receipt was successfully updated!")
                        st.rerun() # Refresh page
    else:
        st.error("Error retrieving data. Check column names.")
