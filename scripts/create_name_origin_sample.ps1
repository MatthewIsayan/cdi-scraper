$source = 'C:\Users\arthu\Downloads\cdi-agents-full-batch - Sheet1.csv'
$outputDir = 'C:\Users\arthu\cdi-scraper\outputs'
$output = Join-Path $outputDir 'cdi-agents-name-origin-full.csv'

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$armenianGiven = @('AKOP','ARAM','ARARAT','ARSEN','GAREGIN','HAGOP','HOVHANNES','LEVON','SARKIS','TIGRAN','VAHE','VARTAN','VOSKAN')
$armenianSurnames = @('VOSKANYAN','SARKISIAN','SARKISYAN','HOVSEPIAN','HOVSEPYAN','GRIGORIAN','GRIGORYAN','PETROSYAN','PETROSIAN','KARAPETIAN','KARAPETYAN','MARGARIAN','MARGARYAN','MANOUKIAN','MANUKYAN','AVANESIAN','AVANESYAN','TER-PETROSYAN')
$spanishSurnames = @('MARTINEZ','GARCIA','RODRIGUEZ','HERNANDEZ','LOPEZ','GONZALEZ','PEREZ','SANCHEZ','RAMIREZ','TORRES','FLORES','RIVERA','GOMEZ','DIAZ','REYES','CRUZ','MORALES','ORTIZ','GUTIERREZ','CHAVEZ','RAMOS','VARGAS','CASTILLO','JIMENEZ','MORENO','ROMERO','ALVAREZ','MENDEZ','RUIZ','HERRERA','MEDINA','AGUILAR','VEGA','NAVARRO','MENDOZA','ESPINOZA','VILLANUEVA','CABRERA','MIRANDA','SALAZAR','MALDONADO','SOTO','VALDEZ','MUNOZ','IBARRA','SANDOVAL','VALENCIA','LEON','CAMPOS','GUZMAN','CERVANTES','SERRANO','CONTRERAS','TREJO','ZAMORA','MOLINA','MONTES','PACHECO','RANGEL','OCHOA','ACOSTA','SOLIS','NUNEZ','MARQUEZ','PADILLA','MERCADO','DURAN','CORTEZ','ROSARIO','DELGADO','FUENTES','PONCE','ESCOBAR','TRUJILLO','MATA','VILLARREAL','FIGUEROA','MADRIGAL','BERNAL','ARANDA','BARRERA','BARRIOS','BAUTISTA','BRAVO','CAMACHO','CARRILLO','CORONADO','DOMINGUEZ','ENCINAS','ESPINOSA','FRANCO','GALLEGOS','HINOJOS','LARA','LOZANO','MARTIN','MONTANO','MURILLO','NIETO','PALACIOS','QUINTERO','ROCHA','SANTIAGO','TAPIA','VILLEGAS','ZUNIGA')

$rows = Import-Csv -LiteralPath $source
$result = foreach ($row in $rows) {
    $name = [string]$row.Name
    $tokens = $name.Trim().ToUpperInvariant() -split '\s+'
    $given = if ($tokens.Count -gt 0) { $tokens[0] } else { '' }
    $surname = if ($tokens.Count -gt 1) { $tokens[-1] } else { '' }
    $label = 'English'

    if ($armenianGiven -contains $given -or $armenianSurnames -contains $surname -or $surname -match '(YAN|IAN)$') {
        $label = 'Armenian'
    } elseif ($spanishSurnames -contains $surname) {
        $label = 'Spanish'
    }

    [pscustomobject]@{
        Name = $name
        'Name-origin reference' = $label
    }
}

$result | Export-Csv -LiteralPath $output -NoTypeInformation -Encoding UTF8
Write-Output $output
