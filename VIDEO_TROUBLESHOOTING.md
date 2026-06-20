# Video Troubleshooting — LG 43UR640S webOS 6.0

## הבעיה המרכזית

הטלוויזיה מריצה וידאו דרך **hardware overlay** — שכבה נפרדת שמוצגת מעל כל ה-HTML.
זה גורם לשני כשלים:
1. **CSS transforms לא מוחלים** על הוידאו (הסיבוב של ה-stage לא עובד)
2. **Canvas לא מכסה** את הוידאו (ה-overlay תמיד מעל הכל)

## ניסיונות שנכשלו

| # | גישה | תוצאה | סיבת הכישלון |
|---|------|--------|---------------|
| 1 | `?signage` + CSS `transform` על `<video>` | סרטון מוצג לא מסובב | hardware overlay מתעלם מ-CSS transforms |
| 2 | Canvas + `ctx.rotate(-π/2)` + `vid.style.display='none'` | **מסך שחור** | `display:none` על `<video>` חוסם גישה לפריימים ב-`drawImage` |
| 3 | Canvas + `preload=auto` (ללא שינוי בhide) | **מסך שחור** | אותה בעיה — `display:none` עדיין חוסם |
| 4 | Canvas + החלפת `display:none` ל-`opacity:0` | לא נבדק על TV | גם אם זה פותר את הפריימים — ה-overlay עדיין מעל הcanvas ב-webOS |
| 5 | `display:none/flex` במקום opacity (ללא canvas) | לא נבדק על TV | הייתה רגרסיה בגישה |
| 6 | FFmpeg `transpose=1` → אפיית סיבוב | שגיאה (קלט=פלט) | תוקן עם temp file, לא נבדק על TV עד כה |

## ניתוח

### למה canvas לא יכול לעבוד על LG webOS

```
stack order על webOS:
┌─────────────────────┐
│   Video HW overlay  │  ← תמיד בראש, לא ניתן לכיסוי
├─────────────────────┤
│   Canvas / HTML     │  ← נמוך יותר, מוסתר מתחת לvideo
└─────────────────────┘
```

גם אם נצליח לצייר פריימים על הcanvas — הוידאו עצמו יכסה אותו.

### למה גרסאות ישנות עבדו (עם סיבוב שגוי)

גרסאות ישנות השתמשו ב-`<video>` ישיר (ללא canvas). הוידאו הוצג דרך הhardware overlay בכיוון שגוי (landscape במסך portrait), אבל לפחות הוצג.

### הפתרון הנכון

**FFmpeg pre-processing + `<video>` ישיר (ללא canvas)**

הלוגיקה:
- vleft (מסך מוטה 90° CW) → `process_video.bat` → `transpose=1` → אפיית 90° CW
- הdisplay מוצג דרך hardware overlay ללא CSS rotation
- סרטון עם 90° CW בפנים + מסך פיזי 90° CW = תמונה זקופה ✓
- על דסקטופ: CSS stage 270° + 90° CW בקובץ = 360° = זקוף ✓ (אותו קובץ עובד בשניהם!)

## Workflow להוספת וידאו

1. קבל MP4 מוואטסאפ או כל מקור
2. גרור על `process_video.bat` (הוא יושב בתיקיית view_left)
3. הוא מעבד → שומר ב-`media/` עם אותו שם
4. הוסף ל-`slides.json` עם `"type": "video"`

## הערות טכניות נוספות

- וידאואים מוואטסאפ: מאוחסנים כ-landscape עם metadata סיבוב, או כ-portrait (464×832)
- LG webOS 6.0: הדפדפן המובנה, לא ניתן לעדכון עצמאי
- Git commits: חייב מ-Windows PowerShell (WSL כותב I/O error על .git/logs ב-OneDrive)
