# tele-puente

Dos piezas pequeñas para una app de tele hecha en casa (Samsung, Tizen):

- **`reproductor.html`**: puente para el reproductor oficial de YouTube. Una app instalada en la tele no tiene dirección web y YouTube no reproduce vídeos dentro de ella (error 153). La app mete esta página en un iframe y la maneja con `postMessage` (poner un vídeo o una lista, pausa, siguiente…). Usa la [API oficial del reproductor de YouTube](https://developers.google.com/youtube/iframe_api_reference) tal cual, con sus anuncios y sus condiciones.
- **`agenda/hoy.json`**: la agenda cultural de hoy en Zaragoza. La tele no puede leer directamente la web del Ayuntamiento, así que GitHub Actions la descarga cada hora con [`agenda/actualizar.py`](agenda/actualizar.py).

Datos de la agenda: [Ayuntamiento de Zaragoza, datos abiertos](https://www.zaragoza.es/sede/portal/datos-abiertos/).

Licencia MIT.
