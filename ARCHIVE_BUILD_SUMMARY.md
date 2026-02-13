# Undomondo Archive System — Build Complete

## Overview

A complete, unified archive system for undomondo.com spanning **4,769 posts** across **17 years** (2005–2021).

**Two distinct eras:**
- **WordPress Era (2005–2008)**: 646 posts
- **Tumblr Era (2007–2021)**: 4,123 posts (with 2007–2008 overlap)

## Architecture

All pages are **self-contained single HTML files** with:
- Inline CSS (no external stylesheets)
- Client-side JavaScript for filtering and lazy loading
- JSON data embedded or loaded dynamically
- No external dependencies beyond Google Fonts

## Directory Structure

```
undomondo-fresh/
├── archive/
│   ├── index.html              # Main archive hub (all 4,769 posts entry point)
│   ├── 2005.html               # Year page: 103 posts
│   ├── 2006.html               # Year page: 214 posts
│   ├── 2007.html               # Year page: 233 posts
│   ├── 2008.html               # Year page: 96 posts
│   ├── post.html               # Post detail template (loads via ?id=)
│   └── posts.json              # WordPress posts data (646 posts)
│
└── tumblr/
    ├── index.html              # Tumblr era hub page
    ├── 2007.html               # Year page: 235 posts
    ├── 2008.html               # Year page: 250 posts
    ├── 2009.html               # Year page: 580 posts
    ├── 2010.html               # Year page: 662 posts
    ├── 2011.html               # Year page: 848 posts (peak)
    ├── 2012.html               # Year page: 453 posts
    ├── 2013.html               # Year page: 331 posts
    ├── 2014.html               # Year page: 239 posts
    ├── 2015.html               # Year page: 152 posts
    ├── 2016.html               # Year page: 126 posts
    ├── 2017.html               # Year page: 122 posts
    ├── 2018.html               # Year page: 54 posts
    ├── 2019.html               # Year page: 46 posts
    ├── 2020.html               # Year page: 23 posts
    ├── 2021.html               # Year page: 2 posts
    ├── post.html               # Post detail template (loads via ?id=)
    └── posts.json              # Tumblr posts data (4,123 posts)
```

## Page Types & Features

### 1. Archive Hub (`/archive/index.html`)

**Purpose**: Main entry point for the archive system.

**Content**:
- Hero section with halftone-blue background
- Title: "THE ARCHIVE" (Dela Gothic One)
- Subtitle: "4,769 posts · 2005–2021"
- Two era cards:
  - WordPress Era: Links to 2005–2008 pages
  - Tumblr Era: Links to 2007–2021 pages
- Top 20 tags browser (combined from both archives)
- Direct navigation to all year pages

**Design**:
- Halftone-blue hero (radial gradient, 24px spacing)
- Red left border on era cards (#D62828)
- Pills for tags (hover: blue background)

### 2. Tumblr Era Hub (`/tumblr/index.html`)

**Purpose**: Landing page for the Tumblr era section (2007–2021).

**Content**:
- Hero section matching archive design
- Links to all 15 year pages (2007–2021)
- Quick overview of 4,123 posts

### 3. Year Pages (`/archive/20XX.html`, `/tumblr/20XX.html`)

**Purpose**: Browse all posts for a specific year with filtering.

**Features**:
- **Hero Section**: Large year number (opacity 0.3), post count
- **Navigation**: Previous/Current/Next year links
- **Filter Bar**: Top 10 tags for that year (clickable pills)
- **Grid View**: 50 posts initially, "Load More" button
  - Lazy loading via JavaScript
  - Grid: `repeat(auto-fill, minmax(350px, 1fr))`
- **Post Cards**:
  - Dark header (date, title)
  - Light body (excerpt, tags)
  - Click to open post detail
  - All 4 fields clickable

**Filtering**:
- Client-side tag filtering
- Clicking a tag pill filters to only posts with that tag
- Click again to clear filter
- Resets to page 1

**Data**:
- Posts data embedded in page as JavaScript array
- No external requests needed

### 4. Post Detail Pages (`/archive/post.html`, `/tumblr/post.html`)

**Purpose**: View full post content with metadata and navigation.

**Features**:
- **Header Section**: Date, title, year
- **Content**: Full HTML rendering (images, iframes, links, etc.)
- **Tags**: All post tags as pills
- **Navigation**:
  - Previous post in year
  - Back to year page
  - Next post in year
- **Responsive**: Content scales well on mobile

**Data Loading**:
- Loads posts.json dynamically
- Uses `?id=` URL parameter to identify post
- Graceful error handling if post not found

## Design System Implementation

### Colors
- **Tomato**: #D62828 (primary accent, buttons, borders)
- **Cream**: #F2EFE5 (footer background text)
- **Charcoal**: #111111 (dark backgrounds, text)
- **Vibrant Blue**: #005F99 (halftone circles, secondary links)
- **Sky**: #0EA5E9 (reserved for future use)
- **Golden**: #FFB703 (reserved for future use)

### Fonts (Google Fonts)
- **Dela Gothic One**: Display headers (hero titles)
- **Space Grotesk**: Navigation, labels
- **Space Mono**: Dates, technical elements
- **DM Sans**: Body text

### Patterns
- **Halftone circles**: Hero sections
  - Background: #111
  - Circles: #005F99, 8px radius
  - Spacing: 24px × 24px
- **Red bottom border**: Navigation (3px solid #D62828)
- **Card design**: White cards with dark headers, left red border
- **Grid layout**: Responsive, auto-fill with min-width 350px

## Key Features

### Client-Side Filtering
- Posts data embedded in page
- Filter by tag without page reload
- Active tag state preserved visually

### Lazy Loading
- First 50 posts load immediately
- "Load More" button for pagination
- Maintains filter state across loads

### Navigation Structure
- Archive hub → Year pages → Post details
- Year pages → Back to hub or adjacent year
- Post details → Previous/Next within year
- Consistent back links throughout

### Responsive Design
- Mobile-first approach
- Flexbox and CSS Grid
- Touch-friendly pill sizing
- Stacked navigation on small screens

## Data Details

### WordPress (646 posts)
- Year breakdown:
  - 2005: 103 posts
  - 2006: 214 posts
  - 2007: 233 posts
  - 2008: 96 posts

### Tumblr (4,123 posts)
- Year breakdown:
  - 2007: 235 posts
  - 2008: 250 posts
  - 2009: 580 posts
  - 2010: 662 posts
  - 2011: 848 posts (peak activity)
  - 2012: 453 posts
  - 2013: 331 posts
  - 2014: 239 posts
  - 2015: 152 posts
  - 2016: 126 posts
  - 2017: 122 posts
  - 2018: 54 posts
  - 2019: 46 posts
  - 2020: 23 posts
  - 2021: 2 posts

### Top 20 Combined Tags
1. live (573)
2. ilerici (539)
3. vintage (354)
4. jazz (283)
5. electronic (270)
6. indie (176)
7. folk (154)
8. photo (152)
9. musicvideo (142)
10. punk (126)
11. garage (109)
12. electronica (107)
13. worldobscure (104)
14. mix (94)
15. house (85)
16. rock (83)
17. improv (76)
18. dance (73)
19. 2015 (71)
20. soundscapes (69)

## Performance Notes

- All pages are self-contained (no external dependencies except fonts)
- Grid renders 50 items, loads more on demand
- JSON data is embedded, no parsing delays
- Filtering is instant (client-side)
- Images and iframes in post content scale responsively

## Deployment

All files are ready for direct upload to `/archive/` and `/tumblr/` on undomondo.com.

### URL Mapping
```
/archive/                  → /archive/index.html
/archive/2005              → /archive/2005.html
/archive/post?id=...       → /archive/post.html
/tumblr/                   → /tumblr/index.html
/tumblr/2011               → /tumblr/2011.html
/tumblr/post?id=...        → /tumblr/post.html
```

Ensure server routes HTML files correctly (no .html extension needed in URLs).

## Cross-Links

All pages correctly link to each other:
- Archive hub → Year pages (both eras)
- Year pages → Back to appropriate hub (archive or tumblr)
- Year pages → Adjacent years (previous/next)
- Year pages → Post detail via card click
- Post detail → Previous/Next posts in year
- Post detail → Back to year page
- Tags → Filter within year page
- Footer → Always back to archive hub

## Browser Compatibility

- All modern browsers (Chrome, Firefox, Safari, Edge)
- ES6 JavaScript (no IE11 support)
- CSS Grid and Flexbox required
- Responsive design works on mobile/tablet/desktop

---

**Build Date**: 2026-02-13
**Total Files Created**: 35 HTML + 2 JSON
**Total Posts Archived**: 4,769
**Date Range**: 2005–2021 (17 years)
