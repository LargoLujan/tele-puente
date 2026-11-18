"""Descarga la agenda municipal de Zaragoza de hoy (datos abiertos del Ayuntamiento) y la deja en agenda/hoy.json.

La usa una app de tele que no puede leer directamente la web del Ayuntamiento. Lo lanza GitHub Actions cada hora.
Uso: python agenda/actualizar.py
"""
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
SALIDA = Path(__file__).resolve().parent / "hoy.json"


def descargar(url):
    peticion = urllib.request.Request(url, headers={"User-Agent": "tele-puente/1.0 (agenda)", "Accept": "application/json"})
    with urllib.request.urlopen(peticion, timeout=120) as respuesta:
        return json.loads(respuesta.read())


def limpio(texto):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", texto or ""))).strip()


def agenda(hoy):
    dia, fecha = DIAS[hoy.weekday()], hoy.strftime("%Y-%m-%d")
    filtro = f"startDate=le={fecha}T23:59:59Z;endDate=ge={fecha}T00:00:00Z"
    datos = descargar("https://www.zaragoza.es/sede/servicio/cultura/evento/list.json?rows=500&q=" + urllib.parse.quote(filtro))
    eventos = []
    for e in datos.get("result", []):
        hora, lugar = None, e.get("location") or ""
        for sub in e.get("subEvent", []):
            for horario in sub.get("openingHours", []) or []:
                if horario.get("dayOfWeek") == dia and horario.get("startTime"):
                    hora = horario["startTime"]
                    lugar = (sub.get("location") or {}).get("title", lugar)
                    break
            if hora:
                break
        tipo = e.get("type", "")
        if not hora or tipo in ("Exposiciones", "Cursos y talleres"):
            continue
        sitio = next((s["location"] for s in e.get("subEvent", []) if s.get("location")), {})
        imagen = e.get("image") or (e.get("program") or {}).get("image") or ""
        eventos.append({
            "titulo": limpio(e.get("title")), "hora": hora, "lugar": limpio(lugar),
            "direccion": limpio(sitio.get("streetAddress")), "barrio": sitio.get("junta", "") or "",
            "transporte": limpio(sitio.get("publicTransport")), "descripcion": limpio(e.get("description"))[:700],
            "imagen": ("https:" + imagen) if imagen.startswith("//") else imagen,
            "programa": (e.get("program") or {}).get("title", ""), "enlace": e.get("alt", ""), "tipo": tipo,
            "destacado": bool(e.get("destacada")),
            "solo_hoy": e.get("startDate", "")[:10] == fecha and e.get("endDate", "")[:10] == fecha,
            "infantil": "infantil" in json.dumps(e, ensure_ascii=False).lower(),
        })
    # primero lo que solo pasa hoy, luego lo destacado, y dentro de cada grupo por hora
    eventos.sort(key=lambda x: (not x["solo_hoy"], not x["destacado"], x["hora"]))
    return eventos[:40]


def main():
    hoy = datetime.now(ZoneInfo("Europe/Madrid"))
    eventos = agenda(hoy)
    if not eventos:
        raise SystemExit("La agenda ha llegado vacía: se deja la anterior")
    SALIDA.write_text(json.dumps({"fecha": hoy.strftime("%Y-%m-%d"), "generado": hoy.strftime("%Y-%m-%d %H:%M"),
                                  "fuente": "Ayuntamiento de Zaragoza, datos abiertos", "eventos": eventos},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(eventos)} actos para el {hoy:%d-%m-%Y}")


if __name__ == "__main__":
    main()
