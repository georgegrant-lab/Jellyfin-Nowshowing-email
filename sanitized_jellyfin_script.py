import os
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

# ==============================
# CONFIGURATION
# ==============================
JELLYFIN_API_URL = os.getenv("JELLYFIN_API_URL", "http://localhost:8096/Users/{USER_ID}/Items/Latest")
JELLYFIN_API_TOKEN = os.getenv("JELLYFIN_API_TOKEN", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
RECIPIENT_EMAILS = os.getenv("RECIPIENT_EMAILS", "").split(",")
JELLYFIN_WEB_URL = os.getenv("JELLYFIN_WEB_URL", "http://localhost:8096/web/index.html")
EMAIL_SUBJECT = os.getenv("EMAIL_SUBJECT", "Now on Jellyfin!")

# Cache folders
POSTER_CACHE_DIR = "cache/posters"
LOGO_CACHE_DIR = "cache/logos"
os.makedirs(POSTER_CACHE_DIR, exist_ok=True)
os.makedirs(LOGO_CACHE_DIR, exist_ok=True)

# ==============================
# FETCH LATEST ITEMS FROM JELLYFIN
# ==============================
def get_latest_items():
    """Fetch latest items from Jellyfin API"""
    try:
        headers = {
            "Authorization": f"MediaBrowser Token={JELLYFIN_API_TOKEN}"
        }
        response = requests.get(JELLYFIN_API_URL, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching latest items: {e}")
        return []

# ==============================
# HELPER: Fetch and cache image
# ==============================
def get_cached_image(url, cache_path, headers=None):
    """Download and cache an image, or return cached version"""
    if not os.path.exists(cache_path):
        try:
            print(f"Downloading: {url}")
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            with open(cache_path, "wb") as f:
                f.write(r.content)
        except Exception as e:
            print(f"Failed to download {url}: {e}")
            return None
    else:
        print(f"Using cached: {cache_path}")
    
    try:
        with open(cache_path, "rb") as f:
            return f.read()
    except Exception as e:
        print(f"Failed to read cached file {cache_path}: {e}")
        return None

# ==============================
# BUILD AND SEND EMAIL
# ==============================
def send_jellyfin_email():
    # Validate required environment variables
    required_vars = ["JELLYFIN_API_URL", "JELLYFIN_API_TOKEN", "SENDER_EMAIL", "SENDER_PASSWORD", "RECIPIENT_EMAILS"]
    for var in required_vars:
        if not os.getenv(var):
            print(f"Error: Environment variable {var} is required but not set.")
            return

    # Get latest items from Jellyfin
    items = get_latest_items()
    
    if not items:
        print("No items found or failed to fetch from Jellyfin")
        return
    
    # Create email message
    msg_root = MIMEMultipart("related")
    msg_root["Subject"] = EMAIL_SUBJECT
    msg_root["From"] = SENDER_EMAIL
    msg_root["To"] = ", ".join(RECIPIENT_EMAILS)
    
    msg_alternative = MIMEMultipart("alternative")
    msg_root.attach(msg_alternative)
    
    # Headers for Jellyfin API requests
    jellyfin_headers = {
        "Authorization": f"MediaBrowser Token={JELLYFIN_API_TOKEN}"
    }
    
    # Extract base URL from JELLYFIN_API_URL for image requests
    jellyfin_base_url = JELLYFIN_API_URL.split("/Users/")[0] if "/Users/" in JELLYFIN_API_URL else "http://localhost:8096"
    
    # Start building HTML content
    html_content = """
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 10px;">
            <h1 style="color: #333; text-align: center;">New Content on Jellyfin!</h1>
            <p style="text-align: center; margin-bottom: 30px;">
                <a href="{}" style="color: #007bff; text-decoration: none;">Open Jellyfin</a>
            </p>
    """.format(JELLYFIN_WEB_URL)
    
    for item in items[:10]:  # Limit to 10 items to avoid huge emails
        item_id = item.get("Id")
        title = item.get("Name", "Unknown Title")
        item_type = item.get("Type", "Unknown")
        
        if not item_id:
            continue
            
        print(f"Processing: {title} (ID: {item_id})")
        
        # Build image URLs using the extracted base URL
        poster_url = f"{jellyfin_base_url}/Items/{item_id}/Images/Primary?maxWidth=300"
        logo_url = f"{jellyfin_base_url}/Items/{item_id}/Images/Logo?maxWidth=300"
        
        # Cache paths
        poster_path = os.path.join(POSTER_CACHE_DIR, f"{item_id}.jpg")
        logo_path = os.path.join(LOGO_CACHE_DIR, f"{item_id}.png")
        
        # Try to get poster image
        poster_bytes = get_cached_image(poster_url, poster_path, jellyfin_headers)
        poster_cid = None
        if poster_bytes:
            poster_cid = f"poster_{item_id}"
            poster_img = MIMEImage(poster_bytes)
            poster_img.add_header("Content-ID", f"<{poster_cid}>")
            msg_root.attach(poster_img)
        
        # Try to get logo image
        logo_bytes = get_cached_image(logo_url, logo_path, jellyfin_headers)
        logo_cid = None
        if logo_bytes:
            logo_cid = f"logo_{item_id}"
            logo_img = MIMEImage(logo_bytes)
            logo_img.add_header("Content-ID", f"<{logo_cid}>")
            msg_root.attach(logo_img)
        
        # Add HTML for this item
        html_content += f"""
        <div style="margin-bottom: 30px; padding: 15px; border: 1px solid #ddd; border-radius: 8px;">
            <div style="display: flex; gap: 15px; align-items: flex-start;">
        """
        
        if poster_cid:
            html_content += f"""
                <div style="flex-shrink: 0;">
                    <img src="cid:{poster_cid}" alt="Poster for {title}" style="max-width: 150px; border-radius: 8px;">
                </div>
            """
        
        html_content += f"""
                <div style="flex-grow: 1;">
                    <h3 style="margin: 0 0 10px 0; color: #333;">{title}</h3>
                    <p style="margin: 0 0 10px 0; color: #666; font-size: 14px;">Type: {item_type}</p>
        """
        
        if logo_cid:
            html_content += f"""
                    <img src="cid:{logo_cid}" alt="Logo for {title}" style="max-width: 200px; margin-top: 10px;">
            """
        
        html_content += """
                </div>
            </div>
        </div>
        """
    
    html_content += """
        </div>
    </body>
    </html>
    """
    
    # Attach HTML content
    msg_alternative.attach(MIMEText(html_content, "html"))
    
    # Send the email
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAILS, msg_root.as_string())
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

# ==============================
# MAIN EXECUTION
# ==============================
if __name__ == "__main__":
    send_jellyfin_email()