import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Importamos TUS módulos
from environment.data import get_air_quality_zmg, get_env_news, get_chapala_level
from chivas.data import get_chivas_news

# Configuración de credenciales
EMAIL_SENDER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASS")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

def create_html_content():
    # 1. Obtener Datos
    air = get_air_quality_zmg()
    chapala = get_chapala_level()
    # Ya no necesitamos use_ai=True aquí porque no mostraremos el resumen, ahorramos tiempo
    env_news = get_env_news(max_items=4, use_ai=False) 
    chivas = get_chivas_news(max_items=4, use_ai=False)
    
    # 2. Construir HTML Minimalista
    html = f"""
    <html>
      <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; line-height: 1.4;">
        
        <div style="margin-bottom: 25px;">
            <h2 style="color: #2c3e50; margin: 0 0 10px 0;">☀️ Reporte: {datetime.now().strftime('%d/%m')}</h2>
            <div style="background-color: #f8f9fa; padding: 10px 15px; border-radius: 6px; border-left: 4px solid #1f77b4; font-size: 14px;">
                🍃 <b>Aire:</b> {air.get('status', 'N/A')} ({air.get('imeca', 'N/A')} IMECA)<br>
                💧 <b>Chapala:</b> {chapala.get('level_msnm', 'N/A')} msnm
            </div>
        </div>

        <h3 style="color: #27ae60; margin-bottom: 15px; font-size: 16px; text-transform: uppercase; letter-spacing: 1px;">
            🌱 Medio Ambiente
        </h3>
    """
    
    if env_news:
        for n in env_news:
            html += f"""
            <div style="margin-bottom: 15px;">
                <div style="font-weight: bold; font-size: 14px; margin-bottom: 2px;">{n['title']}</div>
                <a href="{n['link']}" style="color: #27ae60; text-decoration: none; font-size: 12px;">
                    Leer en {n['source']} &#10138;
                </a>
            </div>
            """
    else:
        html += "<p style='font-size: 12px; color: #777;'>Sin novedades hoy.</p>"

    html += """
        <h3 style="color: #c0392b; margin-top: 30px; margin-bottom: 15px; font-size: 16px; text-transform: uppercase; letter-spacing: 1px;">
            🐐 Chivas
        </h3>
    """
    
    if chivas:
        for n in chivas:
            html += f"""
            <div style="margin-bottom: 15px;">
                <div style="font-weight: bold; font-size: 14px; margin-bottom: 2px;">{n['title']}</div>
                <a href="{n['link']}" style="color: #c0392b; text-decoration: none; font-size: 12px;">
                    Leer en {n['source']} &#10138;
                </a>
            </div>
            """
    else:
        html += "<p style='font-size: 12px; color: #777;'>Sin novedades hoy.</p>"

    # 3. Footer con Link a la App
    html += """
        <br>
        <div style="border-top: 1px solid #eee; padding-top: 20px; text-align: center; font-size: 13px;">
            <p style="margin-bottom: 10px;">Estas son las noticias del dia de hoy Ivan.</p>
            <a href="https://eco-and-rebano-tracker.streamlit.app/" 
               style="background-color: #1f77b4; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
               Acceder al Dashboard Completo
            </a>
            <p style="margin-top: 15px; color: #999; font-size: 11px;">Que tengas un excelente dia.</p>
        </div>
      </body>
    </html>
    """
    return html

def send_email():
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("❌ Error: Faltan credenciales en .env")
        return

    msg = MIMEMultipart()
    msg['From'] = f"GDL Insight - AI Agent"
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = f"📊 Briefing {datetime.now().strftime('%d/%m')}"

    msg.attach(MIMEText(create_html_content(), 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("✅ Correo enviado.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    send_email()