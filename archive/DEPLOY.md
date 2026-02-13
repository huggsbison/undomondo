# Archive Deployment Guide

## What's Built

Your archive is ready! 3 files in this folder:

- `index.html` - Main archive page (V2 magazine style, filterable by tag, searchable)
- `post.html` - Individual post page template (loads dynamically)
- `posts.json` - All 646 posts (2005-2008)

## How to Deploy

### Option 1: Manual Upload to Netlify (Easiest)

1. Go to https://app.netlify.com/sites/undomondo/deploys
2. Drag this entire folder onto the deploy area
3. Done! It will be live at www.undomondo.com/archive

### Option 2: Push to GitHub (If you have the repo)

1. Copy these 3 files to your `undomondo` repo in an `/archive` folder
2. Commit and push
3. Netlify will auto-deploy

## What You'll See

**Archive page**: https://www.undomondo.com/archive
- All 646 posts grouped by year (2008, 2007, 2006, 2005)
- Filter by genre (electronica, jazz, indie, etc.)
- Search box
- Click any post to read it

**Individual posts**: https://www.undomondo.com/archive/post.html?slug=icy-demons
- Full post content
- Tags (clickable to filter)
- Links back to archive

## Features

✓ V2 magazine style (clean, editorial)
✓ Responsive (works on mobile)
✓ Fast (no images to load, just loads JSON once)
✓ SEO-friendly (individual URLs for each post)
✓ Filterable by 9 top genres
✓ Search across all content

## Next Steps

1. Deploy it (see options above)
2. Look at it live on your site
3. Tell me what to change/improve
4. I'll redeploy the changes
5. Repeat until you're happy!

---

Built: 2026-02-13
Posts: 646 (May 2005 - June 2008)
