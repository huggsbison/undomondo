# Undomondo Archive System — Deployment Guide

## Quick Start

The complete archive system is built and ready to deploy. All files are self-contained and require no build process.

## Files to Deploy

### Archive Section
Copy all files from `archive/` to `/archive/` on undomondo.com:
```
archive/index.html           (hub page, 9.1 KB)
archive/2005.html            (103 posts, 252 KB)
archive/2006.html            (214 posts, 928 KB)
archive/2007.html            (233 posts, 970 KB)
archive/2008.html            (96 posts, 401 KB)
archive/post.html            (detail template, 8.0 KB)
archive/posts.json           (646 posts data, 2.4 MB)
```

### Tumblr Section
Copy all files from `tumblr/` to `/tumblr/` on undomondo.com:
```
tumblr/index.html            (hub page, 5.9 KB)
tumblr/2007.html through     (15 year pages, 2007-2021)
tumblr/2021.html
tumblr/post.html             (detail template, 8.0 KB)
tumblr/posts.json            (4,123 posts data, 2.5 MB)
```

## Total Deployment Size

- **Archive**: ~3.6 MB
- **Tumblr**: ~5.0 MB
- **Total**: ~8.6 MB

## Server Configuration

### Netlify (Current Platform)

1. **Add `.html` routing** (optional, for clean URLs):
   - Create `netlify.toml` at root:
   ```toml
   [[redirects]]
     from = "/archive/*"
     to = "/archive/:splat.html"
     status = 200

   [[redirects]]
     from = "/tumblr/*"
     to = "/tumblr/:splat.html"
     status = 200
   ```

2. **Or use direct links** (simpler):
   - `/archive/` → `/archive/index.html`
   - `/archive/2005` → `/archive/2005.html` (or `/archive/2005/`)
   - `/archive/post?id=123` → `/archive/post.html?id=123`

### Traditional Hosting

1. Upload files to server
2. Ensure `.html` files are served with `Content-Type: text/html`
3. Configure rewrite rules if using clean URLs (optional)

### URL Structure

**With clean URLs (via rewrites):**
```
/archive/                     → archive/index.html
/archive/2005/                → archive/2005.html
/archive/post?id=abc123       → archive/post.html
/tumblr/                      → tumblr/index.html
/tumblr/2011/                 → tumblr/2011.html
/tumblr/post?id=xyz789        → tumblr/post.html
```

**Without rewrites (direct URLs):**
```
/archive/index.html
/archive/2005.html
/archive/post.html?id=abc123
/tumblr/index.html
/tumblr/2011.html
/tumblr/post.html?id=xyz789
```

## Pre-Deployment Checks

- [ ] All `.html` files present (23 total)
- [ ] Both `posts.json` files present
- [ ] File sizes match above
- [ ] Server CORS headers allow local font loading (usually fine)
- [ ] Google Fonts CDN accessible from server location

## Post-Deployment Verification

1. **Archive Hub**: Open `/archive/` 
   - Should show hero with "THE ARCHIVE"
   - All era cards clickable
   - Top tags visible

2. **Year Pages**: Open `/archive/2006/`
   - Should list 214 posts in grid
   - Filter pills work
   - "Load More" button appears if posts > 50

3. **Post Detail**: Click any post card
   - Should load full post content
   - Navigation arrows appear if not first/last
   - Date and tags visible

4. **Tumblr Section**: Open `/tumblr/`
   - Should show all 15 year links
   - Peak year is 2011 (848 posts)

5. **Cross-Navigation**:
   - Archive → Year → Post → Back
   - All links work without 404s
   - Navigation bars consistent

## Performance Notes

- First page load may take 2-3s (posts.json is large)
- Subsequent filtering/pagination is instant (client-side)
- Images load on-demand in post details
- No server calls except initial page load

## Troubleshooting

### Posts not showing
- Check `posts.json` file is present and accessible
- Verify JSON isn't corrupted (should start with `[` and end with `]`)
- Check browser console for errors

### Filtering not working
- Ensure JavaScript is enabled
- Check if `allPosts` array loads correctly
- Try in private/incognito window (cache issue?)

### Styling looks wrong
- Verify Google Fonts URL is accessible
- Check if any CSS files are overriding inline styles
- Clear browser cache

### Post detail shows "Post not found"
- Verify post ID in URL query string
- Check posts.json contains the post ID
- Try a different post ID

## Future Updates

To add new posts:
1. Update `posts.json` files with new entries
2. Regenerate year pages (Python script available)
3. Deploy updated files
4. No changes to HTML structure needed

## Backup

Before deploying:
1. Backup existing `/archive/` and `/tumblr/` directories (if any)
2. Keep a local copy of this build
3. Version control preferred (git)

## Contact

All links point back to:
- `/` (home)
- Newsletter signup
- Contact form

Update footer links if contact page URL changes.

---

**Ready to deploy!** All files are tested and functional.
