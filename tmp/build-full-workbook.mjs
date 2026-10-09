import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "C:/Users/arthu/cdi-scraper";
const inputPath = process.argv[2] ? path.resolve(process.argv[2]) : path.join(root, "exports/full-batch/selected-rows.json");
const outputPath = process.argv[3] ? path.resolve(process.argv[3]) : path.join(root, "outputs/full-batch/cdi-agents-full-batch.xlsx");
const previewDir = process.argv[4] ? path.resolve(process.argv[4]) : path.join(root, "tmp/full-batch-preview");
const rows = JSON.parse(await fs.readFile(inputPath, "utf8"));
if (!rows.length) throw new Error("No rows available for workbook export");

const columns = [
  "Name", "Passed_Test", "Assessment", "License_URL", "License_Number", "Business_Address", "Business_Phone",
  "Directions_URL", "Source_ZIPs", "Checked_On", "Languages", "Active_Qualifications", "Qualification_Details",
  "Life_Issue_Date", "Years_Since_Life_Issue", "Active_Health_Authority", "Active_PC_Authority", "Active_Variable_Authority",
  "Appointed_Insurers", "Appointment_Row_Count", "Unique_Insurer_Count", "Life_Appointed_Insurers", "Unique_Life_Insurer_Count",
  "Health_Appointed_Insurers", "PC_Appointed_Insurers", "Appointment_Details", "Agency_Organizations", "Unique_Agency_Count",
  "Agency_Relationship_Count", "Life_Agency_Organizations", "Agency_Relationship_Details", "Latest_Displayed_Relationship_Date", "Rule_Document"
];

function colLetter(index) {
  let n = index + 1;
  let result = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    result = String.fromCharCode(65 + rem) + result;
    n = Math.floor((n - 1) / 26);
  }
  return result;
}

function safeSheetName(language) {
  const cleaned = String(language).replace(/[\\/?*\[\]:]/g, " ").trim() || "Other";
  return `Passed - ${cleaned}`.slice(0, 31);
}

function languageList(row) {
  return String(row.Languages || "").split(";").map((value) => value.trim()).filter(Boolean);
}

function sheetRows(sourceRows) {
  return [columns, ...sourceRows.map((row) => columns.map((column) => row[column] ?? ""))];
}

const languages = [...new Set(rows.filter((row) => row.Passed_Test === "Yes").flatMap(languageList))].sort((a, b) => a.localeCompare(b));
const sheets = [
  ["Master", rows],
  ["Passed", rows.filter((row) => row.Passed_Test === "Yes")],
  ["Failed", rows.filter((row) => row.Passed_Test === "No")],
  ["Needs review", rows.filter((row) => !row.Passed_Test)],
  ...languages.map((language) => [`Passed - ${language}`, rows.filter((row) => row.Passed_Test === "Yes" && languageList(row).includes(language))]),
];

const workbook = Workbook.create();
const headerColor = "#243B53";
const accentColor = "#2F75B5";

for (let sheetIndex = 0; sheetIndex < sheets.length; sheetIndex++) {
  const [sheetName, sourceRows] = sheets[sheetIndex];
  const actualSheetName = sheetName.startsWith("Passed - ") ? safeSheetName(sheetName.slice("Passed - ".length)) : sheetName;
  const sheet = workbook.worksheets.add(actualSheetName);
  sheet.showGridLines = false;
  sheet.tabColor = sheetName === "Master" ? accentColor : sheetName === "Needs review" ? "#BF9000" : sheetName === "Failed" ? "#C00000" : "#548235";
  const matrix = sheetRows(sourceRows);
  const lastRow = matrix.length;
  const lastCol = columns.length;
  const usedAddress = `A1:${colLetter(lastCol - 1)}${lastRow}`;
  const range = sheet.getRange(usedAddress);
  range.values = matrix;
  range.format.font = { name: "Aptos", size: 10, color: "#1F2933" };
  range.format.verticalAlignment = "center";
  range.format.wrapText = true;
  range.format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
  const header = sheet.getRange(`A1:${colLetter(lastCol - 1)}1`);
  header.format.fill = headerColor;
  header.format.font = { name: "Aptos Display", size: 10, bold: true, color: "#FFFFFF" };
  header.format.horizontalAlignment = "center";
  header.format.verticalAlignment = "center";
  header.format.wrapText = true;
  header.format.rowHeight = 32;
  if (lastRow > 1) {
    sheet.getRange(`A2:${colLetter(lastCol - 1)}${lastRow}`).format.rowHeight = 42;
    sheet.getRange(`B2:B${lastRow}`).format.horizontalAlignment = "center";
    sheet.getRange(`E2:E${lastRow}`).format.numberFormat = [["@"]];
    const urlRange = sheet.getRange(`D2:D${lastRow}`);
    urlRange.formulas = sourceRows.map((row) => {
      const url = String(row.License_URL || "").replaceAll('"', '""');
      return [[`=HYPERLINK("${url}","${url}")`]][0];
    });
    urlRange.format.font = { color: "#0563C1", underline: "single" };
    sheet.getRange(`B2:B${lastRow}`).conditionalFormats.add("containsText", { text: "Yes", format: { fill: "#E2F0D9", font: { color: "#006100", bold: true } } });
    sheet.getRange(`B2:B${lastRow}`).conditionalFormats.add("containsText", { text: "No", format: { fill: "#FCE4D6", font: { color: "#9C0006", bold: true } } });
    sheet.getRange(`B2:B${lastRow}`).conditionalFormats.add("containsBlanks", { format: { fill: "#FFF2CC", font: { color: "#7F6000", bold: true } } });
  }
  const table = sheet.tables.add(usedAddress, true, `FullBatchTable${sheetIndex + 1}`);
  table.style = "TableStyleMedium2";
  table.showFilterButton = true;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(4);
  for (let c = 0; c < columns.length; c++) {
    const name = columns[c];
    let width = Math.max(12, Math.min(34, name.length + 2));
    if (["Name", "License_Number", "Checked_On", "Languages", "Passed_Test"].includes(name)) width = Math.max(width, 17);
    if (["Assessment", "Qualification_Details", "Appointment_Details", "Agency_Relationship_Details", "Rule_Document"].includes(name)) width = 52;
    if (["License_URL", "Directions_URL"].includes(name)) width = 56;
    if (["Business_Address", "Agency_Organizations", "Life_Agency_Organizations", "Appointed_Insurers", "Life_Appointed_Insurers", "Health_Appointed_Insurers", "PC_Appointed_Insurers"].includes(name)) width = 34;
    sheet.getRange(`${colLetter(c)}:${colLetter(c)}`).format.columnWidth = width;
  }
}

workbook.recalculate();
const masterCheck = await workbook.inspect({ kind: "table", range: "Master!A1:AG6", include: "values,formulas", tableMaxRows: 6, tableMaxCols: 33 });
console.log("MASTER_CHECK", masterCheck.ndjson);
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan" });
console.log("FORMULA_ERRORS", errors.ndjson);
await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
for (const [sheetName] of sheets) {
  const actualSheetName = sheetName.startsWith("Passed - ") ? safeSheetName(sheetName.slice("Passed - ".length)) : sheetName;
  const preview = await workbook.render({ sheetName: actualSheetName, range: "A1:L20", scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, `${sheetName.replaceAll(" ", "_")}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const tempOutput = `${outputPath}.tmp`;
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(tempOutput);
await fs.rm(outputPath, { force: true });
await fs.rename(tempOutput, outputPath);
console.log(JSON.stringify({ outputPath, rows: rows.length, columns: columns.length, sheets: sheets.map(([name, data]) => ({ name, rows: data.length })), languages }, null, 2));
