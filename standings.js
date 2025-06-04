const TABLE_COLS = [
    "Driver", "Class", "Pos", "Class Pos", "Laps",
    "Pits", "Avg Lap", "Best Lap", "Last Lap", "In Pit"
];

let standingsData = [];
let sortIndex = null;
let sortAsc = true;
let lastColIdx = {};
let lastClassMap = {};

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

        // Map internal class labels to display name and order (1 = fastest)
        const CLASS_MAP = {
            "Hypercar":   { display: "Hypercar", order: 1 },
            "P2":         { display: "P2",       order: 2 },
            "GT3":        { display: "GT3",      order: 3 },
            "Class 2523": { display: "P2",       order: 2 }, // For legacy CSVs!
            "Class 2708": { display: "GT3",      order: 3 },
            "Class 4074": { display: "Hypercar", order: 1 }
        };

        lastColIdx = colIdx;
        lastClassMap = CLASS_MAP;

        // Gather all rows as arrays for easier sorting/filtering
        const rows = [];
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

            rows.push(row);
        }
        standingsData = rows;
        renderStandings();

    } catch (e) {
        // Optionally show error in overlay or log to console
        // console.error(e);
    }
}

function compareValues(a, b, idx, classMap) {
    if (TABLE_COLS[idx] === "Class") {
        const va = classMap[a[idx]] ? classMap[a[idx]].order : 99;
        const vb = classMap[b[idx]] ? classMap[b[idx]].order : 99;
        return va - vb;
    }
    const na = parseFloat(a[idx]);
    const nb = parseFloat(b[idx]);
    if (!isNaN(na) && !isNaN(nb)) {
        return na - nb;
    }
    return String(a[idx]).localeCompare(String(b[idx]));
}

function renderStandings() {
    const colIdx = lastColIdx;
    const CLASS_MAP = lastClassMap;
    const tbody = document.querySelector("#standingsTable tbody");
    tbody.innerHTML = "";

    const rows = [...standingsData];

    if (sortIndex === null) {
        const leaders = {};
        for (const r of rows) {
            const cls = r[colIdx.class];
            const pos = parseInt(r[colIdx.pos], 10);
            if (!(cls in leaders) || pos < leaders[cls]) {
                leaders[cls] = pos;
            }
        }
        const classOrder = Object.entries(leaders)
            .sort((a, b) => a[1] - b[1])
            .map(([cls]) => cls);
        const orderMap = {};
        classOrder.forEach((c, i) => (orderMap[c] = i));
        rows.sort((a, b) => {
            const aClass = orderMap[a[colIdx.class]] ?? 99;
            const bClass = orderMap[b[colIdx.class]] ?? 99;
            if (aClass !== bClass) return aClass - bClass;
            return Number(a[colIdx.pos]) - Number(b[colIdx.pos]);
        });
    } else {
        rows.sort((a, b) => {
            const res = compareValues(a, b, sortIndex, CLASS_MAP);
            return sortAsc ? res : -res;
        });
    }
 // Now render in sorted order, substituting the display class name and color
 // Class icons as emoji placeholders (swap for SVGs if you wish)
const CLASS_ICON = {
    "Hypercar": "🟥",
    "P2":       "🟦",
    "GT3":      "🟩"
};

let lastClassOrder = null;
for (const row of dataRows) {
    const tr = document.createElement('tr');
    const rawClass = row[colIdx.class];
    let classOrder = 99;
    let classDisplay = rawClass;
    if (CLASS_MAP[rawClass]) {
        classOrder = CLASS_MAP[rawClass].order;
        classDisplay = CLASS_MAP[rawClass].display;
    }

    if (classOrder !== lastClassOrder) {
        lastClassOrder = classOrder;
        const headerTr = document.createElement('tr');
        headerTr.classList.add(`class-${classOrder}`, 'group-header');
        const headerTd = document.createElement('td');
        headerTd.colSpan = headers.length;
        headerTd.textContent = classDisplay;
        headerTr.appendChild(headerTd);
        tbody.appendChild(headerTr);
    }

    tr.classList.add(`class-${classOrder}`);
    if (row[colIdx.classPos] === "1") tr.classList.add('leader');

    [
        colIdx.driver,
        null,
        colIdx.pos, colIdx.classPos,
        colIdx.laps, colIdx.pits, colIdx.avgLap,
        colIdx.bestLap, colIdx.lastLap, colIdx.inPit
    ].forEach((idx, i) => {
        const td = document.createElement('td');
        if (i === 1) {
            let icon = '';
            if (CLASS_ICON[classDisplay]) icon = `<span class="class-icon">${CLASS_ICON[classDisplay]}</span>`;
            td.innerHTML = icon + classDisplay;
        } else if (idx !== null) {
            const val = row[idx];
            const num = parseFloat(val);
            td.textContent = isNaN(num) ? val : formatNumber(val);
        }
        if (row[colIdx.classPos] === "1") tr.classList.add("leader");

        [
            colIdx.driver,
            null,
            colIdx.pos, colIdx.classPos,
            colIdx.laps, colIdx.pits, colIdx.avgLap,
            colIdx.bestLap, colIdx.lastLap, colIdx.inPit
        ].forEach((idx, i) => {
            const td = document.createElement('td');
            if (i === 1) {
                let icon = "";
                if (CLASS_ICON[classDisplay]) {
                    icon = `<span class="class-icon">${CLASS_ICON[classDisplay]}</span>`;
                }
                td.innerHTML = icon + classDisplay;
            } else if (idx !== null) {
                const val = row[idx];
                const num = parseFloat(val);
                td.textContent = isNaN(num) ? val : formatNumber(val);
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    }
}

document.querySelectorAll('#standingsTable th.sortable').forEach((th, idx) => {
    th.addEventListener('click', () => {
        if (sortIndex === idx) {
            sortAsc = !sortAsc;
        } else {
            sortIndex = idx;
            sortAsc = true;
        }
        renderStandings();
    });
});

// Update every 5 seconds
setInterval(fetchAndRenderStandings, 5000);
fetchAndRenderStandings();
