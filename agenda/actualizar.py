"""Deja en agenda/hoy.json lo que hay hoy en Zaragoza, para una app de tele que no puede leer estas webs directamente.

Fuentes (datos públicos; solo se copian título, hora, sitio y enlace, y lo que la fuente da como descripción):
- Agenda municipal del Ayuntamiento de Zaragoza (datos abiertos).
- Programación del Teatro Principal de Zaragoza.

Siempre deja el fichero de hoy, aunque una fuente no conteste o no haya nada: así la tele sabe que no es el de ayer.
Si una fuente falla a media jornada, se conserva lo que ya se había leído hoy. Lo lanza GitHub Actions cada hora.
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
ESPERA = 30  # segundos por petición
AYUNTAMIENTO, TEATRO = "Ayuntamiento de Zaragoza", "Teatro Principal"


def descargar(url):
    peticion = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (tele-puente; agenda)", "Accept": "application/json"})
    with urllib.request.urlopen(peticion, timeout=ESPERA) as respuesta:
        return json.loads(respuesta.read())


def limpio(texto):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", texto or ""))).strip()


def es_infantil(*textos):
    t = " ".join(textos).lower()
    return any(p in t for p in ("infantil", "familiar", "en familia", "niños", "niñas", "peques", "títeres", "titeres"))


def evento(titulo, hora, lugar, **resto):
    base = {"titulo": titulo, "hora": hora, "lugar": lugar, "direccion": "", "barrio": "", "transporte": "", "descripcion": "",
            "imagen": "", "programa": "", "enlace": "", "tipo": "", "destacado": False, "solo_hoy": True, "infantil": False}
    base.update(resto)
    return base


def agenda_ayuntamiento(hoy):
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
        eventos.append(evento(
            limpio(e.get("title")), hora, limpio(lugar),
            direccion=limpio(sitio.get("streetAddress")), barrio=sitio.get("junta", "") or "",
            transporte=limpio(sitio.get("publicTransport")), descripcion=limpio(e.get("description"))[:700],
            imagen=("https:" + imagen) if imagen.startswith("//") else imagen,
            programa=(e.get("program") or {}).get("title", ""), enlace=e.get("alt", ""), tipo=tipo,
            destacado=bool(e.get("destacada")),
            solo_hoy=e.get("startDate", "")[:10] == fecha and e.get("endDate", "")[:10] == fecha,
            infantil="infantil" in json.dumps(e, ensure_ascii=False).lower(),
        ))
    return eventos


def teatro_principal(hoy):
    fecha = hoy.strftime("%Y-%m-%d")
    url = ("https://teatroprincipalzaragoza.com/wp-json/tribe/events/v1/events?per_page=50&start_date="
           + urllib.parse.quote(fecha + " 00:00:00") + "&end_date=" + urllib.parse.quote(fecha + " 23:59:59"))
    eventos = []
    for e in descargar(url).get("events", []):
        if not str(e.get("start_date", "")).startswith(fecha):
            continue
        titulo, texto = limpio(e.get("title")), limpio(e.get("description") or e.get("excerpt"))
        imagen = e.get("image") if isinstance(e.get("image"), dict) else {}
        eventos.append(evento(
            titulo, "Todo el día" if e.get("all_day") else e["start_date"][11:16], TEATRO,
            direccion="Coso, 57", barrio="Casco Histórico", descripcion=texto[:700], imagen=imagen.get("url", ""),
            enlace=e.get("url", ""), tipo="Teatro", infantil=es_infantil(titulo, texto),
        ))
    return eventos


def main():
    hoy = datetime.now(ZoneInfo("Europe/Madrid"))
    fecha = hoy.strftime("%Y-%m-%d")
    eventos, fuentes = [], {}
    for nombre, leer in ((AYUNTAMIENTO, agenda_ayuntamiento), (TEATRO, teatro_principal)):
        try:
            lista = leer(hoy)
            fuentes[nombre] = len(lista)
            eventos += lista
        except Exception as error:  # una web caída no debe dejar la agenda sin publicar
            fuentes[nombre] = None
            print(f"{nombre}: sin respuesta ({type(error).__name__}: {error})")

    # Si una fuente ha fallado ahora pero esta mañana sí contestó, se conserva lo de esta mañana
    try:
        anterior = json.loads(SALIDA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        anterior = {}
    if anterior.get("fecha") == fecha and None in fuentes.values() and len(anterior.get("eventos", [])) > len(eventos):
        print(f"Se conserva la agenda leída antes ({len(anterior['eventos'])} actos)")
        return

    # sin repetidos (el Ayuntamiento también anuncia lo del teatro); primero lo que solo pasa hoy, luego lo destacado, por hora
    vistos, unicos = set(), []
    for e in eventos:
        clave = (re.sub(r"\W+", "", e["titulo"].lower()), e["hora"])
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(e)
    unicos.sort(key=lambda x: (not x["solo_hoy"], not x["destacado"], x["hora"]))
    SALIDA.write_text(json.dumps({"fecha": fecha, "generado": hoy.strftime("%Y-%m-%d %H:%M"), "fuentes": fuentes,
                                  "eventos": unicos[:40]}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(unicos)} actos para el {hoy:%d-%m-%Y} · {fuentes}")


if __name__ == "__main__":
    main()
