from __future__ import annotations

import html
import os
import re
import xml.etree.ElementTree as ET

import requests
import signxml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from signxml import XMLSigner

from src.core.logging import get_logger

logger = get_logger(__name__)

URL_SEED = "https://maullin.sii.cl/DTEWS/CrSeed.jws"
URL_TOKEN = "https://maullin.sii.cl/DTEWS/GetTokenFromSeed.jws"
REQUEST_TIMEOUT_SECONDS = 20


class SiiAuthError(RuntimeError):
    """Error controlado de autenticación con el SII (sin datos sensibles)."""


def _certificate_config() -> tuple[str, str]:
    pfx_path = os.getenv("SII_CERT_PATH", "").strip()
    pfx_pass = os.getenv("SII_CERT_PASSWORD", "")
    if not pfx_path:
        raise SiiAuthError(
            "La autenticación con el SII requiere SII_CERT_PATH y SII_CERT_PASSWORD "
            "con un certificado digital válido."
        )
    if not os.path.exists(pfx_path):
        raise SiiAuthError(
            "No se encontró el certificado del SII en SII_CERT_PATH. "
            "Configura un certificado digital válido para autenticarte."
        )
    return pfx_path, pfx_pass


def get_sii_seed() -> str:
    """Obtiene la semilla aleatoria real del SII."""
    soap_body = """<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://sii.cl/">
       <soap:Body>
          <tns:getSeed/>
       </soap:Body>
    </soap:Envelope>"""

    headers = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": ""}
    try:
        response = requests.post(URL_SEED, data=soap_body, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.warning("No se pudo conectar con el SII para obtener la semilla")
        raise SiiAuthError("No se pudo conectar con el SII para obtener la semilla.") from exc

    if response.status_code == 200:
        unescaped_text = html.unescape(response.text)
        match = re.search(r"<SEMILLA>(\d+)</SEMILLA>", unescaped_text)
        if match:
            return match.group(1)

    logger.warning("El SII rechazó la solicitud de semilla (status=%s)", response.status_code)
    raise SiiAuthError("El SII rechazó la solicitud de semilla. Verifica el certificado y reintenta.")


def sign_xml_seed(seed: str, pfx_path: str, password: str) -> str:
    """Firma digitalmente la semilla con el certificado del contribuyente."""
    try:
        with open(pfx_path, "rb") as handle:
            pfx_data = handle.read()
        private_key, certificate, _additional_certs = pkcs12.load_pkcs12(
            pfx_data, password.encode() if password else None
        )
    except Exception as exc:  # pragma: no cover - depende del certificado real
        logger.warning("No se pudo cargar el certificado del SII")
        raise SiiAuthError("No se pudo cargar el certificado del SII. Verifica el archivo y la contraseña.") from exc

    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)

    xml_content = f"<getToken><item><semilla>{seed}</semilla></item></getToken>"
    element_to_sign = ET.fromstring(xml_content)

    signer = XMLSigner(method=signxml.methods.enveloped, signature_algorithm="rsa-sha1")
    signed_root = signer.sign(element_to_sign, key=key_pem, cert=cert_pem)
    return ET.tostring(signed_root, encoding="utf-8").decode("utf-8")


def get_sii_token(signed_xml_str: str) -> str:
    """Canjea la semilla firmada por un token en el SII."""
    soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://sii.cl/">
       <soap:Body>
          <tns:getToken>
             <pszXml>{signed_xml_str}</pszXml>
          </tns:getToken>
       </soap:Body>
    </soap:Envelope>"""

    headers = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": ""}
    try:
        response = requests.post(URL_TOKEN, data=soap_body, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.warning("No se pudo conectar con el SII para canjear el token")
        raise SiiAuthError("No se pudo conectar con el SII para obtener el token.") from exc

    if response.status_code == 200:
        unescaped_text = html.unescape(response.text)
        match = re.search(r"<TOKEN>([^<]+)</TOKEN>", unescaped_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    logger.warning("El SII rechazó el canje de token (status=%s)", response.status_code)
    raise SiiAuthError("El SII rechazó el canje de token. Verifica el certificado y reintenta.")


def authenticate_in_sii() -> str:
    """Autentica contra el SII usando un certificado digital real.

    No existe modo simulado: si falta el certificado o la configuración, se
    lanza un error explícito en lugar de devolver un token falso.
    """
    pfx_path, pfx_pass = _certificate_config()

    seed = get_sii_seed()
    logger.info("Semilla del SII obtenida correctamente")
    signed_xml = sign_xml_seed(seed, pfx_path, pfx_pass)
    token = get_sii_token(signed_xml)
    logger.info("Token del SII obtenido correctamente")
    return token
