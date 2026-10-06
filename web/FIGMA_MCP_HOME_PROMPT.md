# Figma MCP Prompt: Home Page (Fire Safety AI)

Use this prompt directly in Figma MCP to generate the homepage frame and components.

## Prompt
Create a responsive web homepage design for a "Fire Safety AI Analysis" product.

### Frame
- Desktop frame: 1440x1800
- Mobile frame: 390x1600
- 12-column grid desktop, 4-column mobile
- Outer container width: 1080, centered

### Visual Direction
- Style: modern, trustable, engineering-focused
- Color palette:
  - Brand primary: #0F766E
  - Brand dark: #0A5B55
  - Accent warning: #B45309
  - Danger: #BE123C
  - Safe: #047857
  - Background gradient from #EEF6F4 to #FDF7EC
- Radius:
  - card: 20
  - input/button: 12
- Shadow:
  - card shadow: 0,12,38,12% dark teal

### Typography
- Font family: Plus Jakarta Sans + Noto Sans SC fallback
- H1: 32/40 800
- Card title: 15/22 800 uppercase
- Body: 14/22 500
- Code block text: 12/18 monospace

### Layout Sections (top to bottom)
1. Hero Header Card
   - Title: "图片 AI 识别"
   - Subtitle: "上传图片后直接显示模型输出"
   - Gradient background (#0B7A70 -> #0A5B55 -> #114B57)

2. Backend Config Card
   - Label: BASE_URL
   - Input + Save button
   - Status hint text area

3. Upload Card
   - File input
   - Scene select (campus, office, factory, residential)
   - Primary CTA button "开始识别"
   - Status hint line

4. Result Card
   - Result image preview area
   - Risk badge (safe/warning/danger variants)
   - Summary text
   - Risk item list cards
   - Citation list cards
   - Stage1 preview code block
   - Raw output code block
   - Debug JSON code block

### Components
- Buttons: default + primary
- Inputs: text input, file input, select
- Badge component:
  - safe: green tint
  - warning: amber tint
  - danger: red tint
- Result item card with left accent bar
- Debug panel with dark background (#132D2A) and mint text

### Interaction States
- Button hover: slight raise + stronger border
- Card hover (optional): subtle elevation
- Loading text state in upload card
- Empty result placeholder state

### Auto Layout Rules
- Use auto layout for each card
- 14px gap between result subsections
- Mobile: stack all controls to full width

### Export
- Provide reusable component set and style tokens.

