import html
import os
import re
import xml.etree.ElementTree as ET

import requests
import signxml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from signxml import XMLSigner

URL_SEED = "https://maullin.sii.cl/DTEWS/CrSeed.jws"
URL_TOKEN = "https://maullin.sii.cl/DTEWS/GetTokenFromSeed.jws"

def get_sii_seed():
    """Obtener la semilla aleatoria real del SII"""
    soap_body = """<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://sii.cl/">
       <soap:Body>
          <tns:getSeed/>
       </soap:Body>
    </soap:Envelope>"""
    
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": ""
    }
    
    response = requests.post(URL_SEED, data=soap_body, headers=headers)
    if response.status_code == 200:
        unescaped_text = html.unescape(response.text)
        match = re.search(r'<SEMILLA>(\d+)</SEMILLA>', unescaped_text)
        if match:
            return match.group(1)
                
    raise Exception(f"Error al obtener semilla del SII: {response.text}")

def sign_xml_seed(seed: str, pfx_path: str, password: str) -> str:
    """Firmar digitalmente la semilla"""
    with open(pfx_path, "rb") as f:
        pfx_data = f.read()
    
    private_key, certificate, additional_certs = pkcs12.load_pkcs12(
        pfx_data, password.encode() if password else None
    )
    
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    
    xml_content = f'<getToken><item><semilla>{seed}</semilla></item></getToken>'
    element_to_sign = ET.fromstring(xml_content)
    
    signer = XMLSigner(method=signxml.methods.enveloped, signature_algorithm="rsa-sha1")
    signed_root = signer.sign(
        element_to_sign,
        key=key_pem,
        cert=cert_pem
    )
    
    return ET.tostring(signed_root, encoding="utf-8").decode("utf-8")

def get_sii_token(signed_xml_str: str) -> str:
    """Canjear token en el SII"""
    soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://sii.cl/">
       <soap:Body>
          <tns:getToken>
             <pszXml>{signed_xml_str}</pszXml>
          </tns:getToken>
       </soap:Body>
    </soap:Envelope>"""
    
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": ""
    }
    
    response = requests.post(URL_TOKEN, data=soap_body, headers=headers)
    if response.status_code == 200:
        unescaped_text = html.unescape(response.text)
        match = re.search(r'<TOKEN>([^<]+)</TOKEN>', unescaped_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
            
    raise Exception(f"Error al obtener el Token del SII: {response.text}")

def authenticate_in_sii() -> str:
    """Función inteligente con soporte de Modo Mock para desarrollo"""
    pfx_path = os.getenv("SII_CERT_PATH", "./certificado.pfx")
    pfx_pass = os.getenv("SII_CERT_PASSWORD", "")
    
    # MODO SIMULACIÓN: Si no existe el archivo físico, devuelve un token simulado para pruebas
    if not os.path.exists(pfx_path):
        print("⚠️ [AVISO]: No se encontró certificado .pfx. Activando MODO SIMULACIÓN (Mock) para desarrollo de NEXORA.")
        return "T_MOCK_TOKEN_NEXORA_DEVELOPMENT_99999"

    print("1. Solicitando semilla real al SII...")
    seed = get_sii_seed()
    print(f"Semilla obtenida: {seed}")
    
    print("2. Firmando semilla digitalmente...")
    signed_xml = sign_xml_seed(seed, pfx_path, pfx_pass)
    
    print("3. Canjeando token en el SII...")
    token = get_sii_token(signed_xml)
    print(f"Token real obtenido con éxito: {token}")
    
    return token