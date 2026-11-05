# Octoparse task: PlanningAlerts national list, keyword matches only

Start URL: `https://www.planningalerts.org.au/applications?page=1`
(30 applications per page, newest first; ~35–45 pages ≈ one weekday)

## 1. Pages
Use a URL list (Batch URL input) of
`https://www.planningalerts.org.au/applications?page=1` … `?page=60`
(60 covers a Monday after a weekend). Set a wait of 3–5 seconds per page.

## 2. Loop Item: only applications whose description has a keyword
Loop mode: **Variable list**, XPath:

```
//main//a[contains(@href,'/applications/')][.//p[contains(@class,'text-navy')][contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'childcare') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'child care') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'child-care') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'early learning') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'early education') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'early childhood') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'kindergarten') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'preschool') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'pre-school') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'medical') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'clinic') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'health') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'hospital') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'veterinary') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'vet clinic') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'vet hospital') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'animal hospital') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'general practice') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'dental') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'physiotherapy') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'pharmacy') or contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'consulting room')]]
```

Not case sensitive. Keywords: childcare, child care, child-care, early learning,
early education, early childhood, kindergarten, preschool, pre-school, medical,
clinic, health, hospital, veterinary, vet clinic, vet hospital, animal hospital,
general practice, dental, physiotherapy, pharmacy, consulting room.
("GP" and "vet" on their own are left out: XPath can't match whole words, so
they would hit "velvet", "revetment" etc.)

## 3. Click item → extract on the application page
| Field | XPath |
|---|---|
| Address | `//main//h1` |
| Description | `//dt[normalize-space()='Description']/following-sibling::dd[1]//text()[normalize-space()][1]` |
| Council | `//dt[normalize-space()='Planning Authority']/following-sibling::dd[1]//text()[normalize-space()][1]` |
| Reference | `//dt[normalize-space()='Reference number']/following-sibling::dd[1]//text()[normalize-space()][1]` |
| Council link | `//a[contains(@href,'/external')]/@href` (prefix https://www.planningalerts.org.au) |
| PlanningAlerts link | page URL |

(Selectors checked against a live application page on 5 Nov 2026.)

## 4. Duplicates
Each daily run overlaps yesterday's pages. Turn on Octoparse's duplicate
removal, and/or have Make search the monday board for the Reference + Council
before creating an item.
