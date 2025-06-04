function formatNumber(value) {
    const num = parseFloat(value);
    if (isNaN(num)) return value;
    let str = num.toFixed(3);
    if (str.includes('.')) {
        str = str.replace(/0+$/, '').replace(/\.$/, '');
    }
    return str;
}

async function fetchAndRenderStandings() {
    try {
        const response = await fetch('sorted_standings.csv?_=' + new Date().getTime());
        const csv = await response.text();

        const lines = csv.trim().split('\n');
        if (lines.length < 2) return; // No data

        const headers = lines[0].split(',').map(h => h.trim());

        // Indexes for all columns we want, regardless of order
        const colIdx = {
            driver: headers.indexOf("Driver"),
            class: headers.indexOf("Class"),
            pos: headers.indexOf("Pos"),
            classPos: headers.indexOf("Class Pos"),
            laps: headers.indexOf("Laps"),
            pits: headers.indexOf("Pits"),
            avgLap: headers.indexOf("Avg Lap"),
            bestLap: headers.indexOf("Best Lap"),
            lastLap: headers.indexOf("Last Lap"),
            inPit: headers.indexOf("In Pit")
        };

        // Map your internal class labels to display and sort order
        const CLASS_MAP = {
            "Hypercar":   { display: "Hypercar", order: 1 },
            "P2":         { display: "P2",       order: 2 },
            "GT3":        { display: "GT3",      order: 3 },
            "Class 2523": { display: "P2",       order: 2 }, // For legacy CSVs!
            "Class 2708": { display: "GT3",      order: 3 },
            "Class 4074": { display: "Hypercar", order: 1 }
        };

        const tbody = document.querySelector("#standingsTable tbody");
        tbody.innerHTML = "";

        // Gather all rows as objects for easier sorting/filtering
        const dataRows = [];
        for (let i = 1; i < lines.length; i++) {
            const row = lines[i].split(',').map(cell => cell.trim());
            if (row.length < headers.length) continue;
            // Filter: skip if Driver is Lily Bowling or Pace Car
            const driverName = row[colIdx.driver];
            if (driverName === "Lily Bowling" || driverName === "Pace Car") continue;
            // Hide entries with position 0 or non-positive lap count
            const pos = parseInt(row[colIdx.pos], 10);
            const laps = parseFloat(row[colIdx.laps]);
            if (pos === 0 || laps <= 0) continue;

            dataRows.push(row);
        }

        // Sort by custom class order, then by class position
        dataRows.sort((a, b) => {
            // Get mapped class order
            const aClass = CLASS_MAP[a[colIdx.class]] ? CLASS_MAP[a[colIdx.class]].order : 99;
            const bClass = CLASS_MAP[b[colIdx.class]] ? CLASS_MAP[b[colIdx.class]].order : 99;
            if (aClass !== bClass) return aClass - bClass;
            // Then sort by class position numerically
            return Number(a[colIdx.classPos]) - Number(b[colIdx.classPos]);
        });

        // Now render in sorted order, substituting the display class name and color
 // Class icons as emoji placeholders (swap for SVGs if you wish)
const CLASS_ICON = {
    "Hypercar": "🟥",
    "P2":       "🟦",
    "GT3":      "🟩"
};

for (const row of dataRows) {
    const tr = document.createElement('tr');
    // Add FFXIV class color (ensure lower case key matches CSS)
    const rawClass = row[colIdx.class];
    let classKey = '';
    let classDisplay = rawClass;
    if (CLASS_MAP[rawClass]) {
        classKey = CLASS_MAP[rawClass].display.toLowerCase();
        classDisplay = CLASS_MAP[rawClass].display;
        tr.classList.add(`class-${classKey}`);
    }
    // Highlight class leaders
    if (row[colIdx.classPos] === "1") tr.classList.add("leader");

    [
        colIdx.driver,
        null, // For class, handled below
        colIdx.pos, colIdx.classPos,
        colIdx.laps, colIdx.pits, colIdx.avgLap,
        colIdx.bestLap, colIdx.lastLap, colIdx.inPit
    ].forEach((idx, i) => {
        const td = document.createElement('td');
        if (i === 1) {
            // Add class icon
            let icon = "";
            if (CLASS_ICON[classDisplay]) icon = `<span class="class-icon">${CLASS_ICON[classDisplay]}</span>`;
            td.innerHTML = icon + classDisplay;
        }
        else if (idx !== null) {
            const val = row[idx];
            const num = parseFloat(val);
            td.textContent = isNaN(num) ? val : formatNumber(val);
        }
        tr.appendChild(td);
    });
    tbody.appendChild(tr);
}

    } catch (e) {
        // Optionally show error in overlay or log to console
        // console.error(e);
    }
}
// Update every 5 seconds
setInterval(fetchAndRenderStandings, 5000);
fetchAndRenderStandings();
