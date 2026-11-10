// Pegar este código en Extensions > Apps Script del Google Sheet donde se
// guardarán las respuestas, y publicarlo como "Web app" (ver README.md).

var SHEET_NAME = 'Respuestas';

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);

    sheet.appendRow([
      new Date(),
      data.situacion || '',
      data.tamanoEquipo || '',
      data.pais || '',
      data.decidePrecio || '',
      data.decideFecha || '',
      data.tiempoInvestigar || '',
      data.infoTranquilidad || '',
      data.usarias1a5 || '',
      data.pagarias || '',
      data.contacto || '',
    ]);

    return ContentService.createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
