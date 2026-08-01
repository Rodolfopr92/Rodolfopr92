#!/usr/bin/env python3
from __future__ import annotations
import json, math, os, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "brand" / "config"
OUT = ROOT / "assets" / "generated"

def read_json(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def rgb(value):
    value=value.lstrip("#")
    return tuple(int(value[i:i+2],16) for i in (0,2,4))

def font_match(family):
    try:
        r=subprocess.run(
            ["fc-match","-f","%{family[0]}|%{file}\\n",family],
            capture_output=True,check=True,text=True
        )
    except (FileNotFoundError,subprocess.CalledProcessError):
        return None
    lines=[x.strip() for x in r.stdout.splitlines() if x.strip()]
    if not lines or "|" not in lines[0]:
        return None
    resolved_family,resolved_file=lines[0].split("|",1)
    norm=lambda value: "".join(ch for ch in value.lower() if ch.isalnum())
    requested=norm(family)
    resolved=norm(resolved_family)
    if requested not in resolved and resolved not in requested:
        return None
    path=Path(resolved_file)
    return path if path.is_file() else None

def resolve_font(path_env,family_env,fallbacks):
    explicit=os.getenv(path_env,"").strip()
    if explicit:
        p=Path(explicit).expanduser().resolve()
        if not p.is_file(): raise FileNotFoundError(f"{path_env}: {p}")
        return p
    preferred=os.getenv(family_env,"").strip()
    for family in ([preferred] if preferred else [])+fallbacks:
        p=font_match(family)
        if p: return p
    raise RuntimeError(f"No font for {family_env}")

def fit_font(path,text_value,max_size,max_width):
    for size in range(max_size,7,-1):
        font=ImageFont.truetype(str(path),size)
        box=font.getbbox(text_value)
        if box[2]-box[0] <= max_width: return font
    return ImageFont.truetype(str(path),8)

def gradient(width,height,theme,light=False):
    if light:
        left,middle,right=(244,239,231),(234,223,211),(218,197,184)
    else:
        left,middle,right=rgb(theme["background"]),rgb(theme["background2"]),rgb(theme["oxblood"])
    image=Image.new("RGB",(width,height))
    px=image.load()
    for x in range(width):
        p=x/max(1,width-1)
        if p<.55:
            t=p/.55
            c=tuple(round(left[i]+(middle[i]-left[i])*t) for i in range(3))
        else:
            t=(p-.55)/.45
            c=tuple(round(middle[i]+(right[i]-middle[i])*t) for i in range(3))
        for y in range(height): px[x,y]=c
    glow=Image.new("RGBA",(width,height),(0,0,0,0))
    gd=ImageDraw.Draw(glow)
    radius=int(min(width,height)*.85); cx,cy=int(width*.78),int(height*.30)
    gd.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),fill=(*rgb(theme["signal"]),82))
    glow=glow.filter(ImageFilter.GaussianBlur(max(16,int(height*.12))))
    image=Image.alpha_composite(image.convert("RGBA"),glow)
    grid=Image.new("RGBA",(width,height),(0,0,0,0)); gr=ImageDraw.Draw(grid)
    step=max(24,int(width/30)); gold=(*rgb(theme["gold"]),16)
    for x in range(0,width,step): gr.line((x,0,x,height),fill=gold,width=1)
    for y in range(0,height,step): gr.line((0,y,width,y),fill=gold,width=1)
    return Image.alpha_composite(image,grid)

def orbit_layer(size,theme,angle,letter,display_path):
    layer=Image.new("RGBA",(size,size),(0,0,0,0)); draw=ImageDraw.Draw(layer)
    c=size//2; gold=rgb(theme["gold"]); gold_hi=rgb(theme["goldHighlight"])
    draw.ellipse((c-size*.34,c-size*.34,c+size*.34,c+size*.34),outline=(*gold,70),width=max(1,size//170))
    draw.ellipse((c-size*.23,c-size*.23,c+size*.23,c+size*.23),outline=(*gold,110),width=max(1,size//170))
    for rot,alpha in [(-16+angle,155),(35-angle*.55,105)]:
        temp=Image.new("RGBA",(size,size),(0,0,0,0)); td=ImageDraw.Draw(temp)
        td.ellipse((c-size*.43,c-size*.12,c+size*.43,c+size*.12),outline=(*gold_hi,alpha),width=max(2,size//125))
        temp=temp.rotate(rot,resample=Image.Resampling.BICUBIC,center=(c,c))
        layer=Image.alpha_composite(layer,temp)
    draw=ImageDraw.Draw(layer)
    theta=math.radians(angle*2.2); nx=c+math.cos(theta)*size*.39; ny=c+math.sin(theta)*size*.16
    draw.ellipse((nx-size*.012,ny-size*.012,nx+size*.012,ny+size*.012),fill=gold_hi)
    shield=[(c,c-size*.24),(c+size*.12,c-size*.17),(c+size*.12,c+size*.06),(c,c+size*.14),(c-size*.12,c+size*.06),(c-size*.12,c-size*.17)]
    draw.polygon(shield,fill=rgb("#170910"),outline=gold_hi)
    font=ImageFont.truetype(str(display_path),int(size*.18)); box=draw.textbbox((0,0),letter,font=font)
    draw.text((c-(box[2]-box[0])/2,c-(box[3]-box[1])/2-size*.035),letter,font=font,fill=gold_hi)
    return layer

def draw_text(draw,xy,value,font,fill,anchor="la"): draw.text(xy,value,font=font,fill=fill,anchor=anchor)

def save_full_bleed(image,path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); image=image.convert("RGB")
    if path.suffix.lower() in {".jpg",".jpeg"}: image.save(path,"JPEG",quality=94,optimize=True,subsampling=0)
    else: image.save(path,"PNG",optimize=True)

def build_hero(brand,display,serif,tech,light=False,angle=0):
    theme=brand["theme"]; identity=brand["identity"]; w,h=2400,860
    image=gradient(w,h,theme,light); draw=ImageDraw.Draw(image)
    gold=rgb(theme["gold"]); gold_hi=rgb(theme["goldHighlight"])
    ivory=rgb("#241116" if light else theme["ivory"]); muted=rgb("#4d3638" if light else theme["muted"])
    draw.rectangle((48,52,w-48,h-52),outline=(*gold,95),width=2)
    draw_text(draw,(142,170),identity["eyebrow"],ImageFont.truetype(str(tech),26),gold)
    draw_text(draw,(142,310),"RODOLFO P.",fit_font(display,"RODOLFO P.",126,1040),ivory)
    draw_text(draw,(142,445),"RODRIGUES",fit_font(display,"RODRIGUES",126,1040),gold_hi)
    role=fit_font(serif,identity["roles"][0],40,1040)
    draw_text(draw,(148,615),identity["roles"][0],role,muted); draw_text(draw,(148,675),identity["roles"][1],role,muted)
    draw.line((148,748,1110,748),fill=(*gold,115),width=2)
    domains=" · ".join(identity["domains"]); draw_text(draw,(148,805),domains,fit_font(tech,domains,24,1060),gold_hi)
    image.alpha_composite(orbit_layer(690,theme,angle,"R",display),(1450,65))
    return image

def build_architecture(brand,serif,tech):
    theme=brand["theme"]; w,h=2400,500; image=gradient(w,h,theme); draw=ImageDraw.Draw(image)
    gold=rgb(theme["gold"]); gold_hi=rgb(theme["goldHighlight"]); ivory=rgb(theme["ivory"]); muted=rgb(theme["muted"])
    draw.rectangle((36,36,w-36,h-36),outline=(*gold,75),width=2)
    label=ImageFont.truetype(str(tech),22); title=ImageFont.truetype(str(serif),32); detail=ImageFont.truetype(str(tech),19)
    draw_text(draw,(120,105),"AUTHORITY FLOWS DOWN · EVIDENCE FLOWS UP",label,gold)
    columns=[("FRONTEND","React · TypeScript","Interaction · State · Visualization"),("BOUNDARY","Services · Contracts","IPC · HTTP · Validation · Events"),("BACKEND","Rust · Node.js · AI","Authority · Security · Orchestration"),("DATA","Operational · Analytical","Evidence · Semantic · Graph")]
    boxw,bh,y=480,210,172
    for i,(a,b,c) in enumerate(columns):
        x=120+i*560; draw.rounded_rectangle((x,y,x+boxw,y+bh),radius=28,fill=rgb("#241018"),outline=gold,width=2)
        draw_text(draw,(x+38,y+52),a,label,gold); draw_text(draw,(x+38,y+116),b,title,ivory); draw_text(draw,(x+38,y+168),c,detail,muted)
        if i<3:
            ax=x+boxw+36; cy=y+bh//2; draw.line((ax,cy,ax+48,cy),fill=gold_hi,width=10); draw.polygon([(ax+48,cy-22),(ax+82,cy),(ax+48,cy+22)],fill=gold_hi)
    return image

def build_project_card(brand,system,display,tech):
    theme=brand["theme"]; w,h=1160,520; image=gradient(w,h,theme); draw=ImageDraw.Draw(image)
    gold=rgb(theme["gold"]); gold_hi=rgb(theme["goldHighlight"]); ivory=rgb(theme["ivory"])
    draw.rounded_rectangle((28,28,w-28,h-28),radius=28,outline=(*gold,85),width=2)
    draw_text(draw,(68,360),system["title"],fit_font(display,system["title"],62,680),ivory)
    draw_text(draw,(68,424),system["subtitle"],fit_font(tech,system["subtitle"],23,690),gold_hi)
    draw.line((68,466,640,466),fill=(*gold,90),width=2)
    image.alpha_composite(orbit_layer(360,theme,0,system["letter"],display),(760,30)); return image

def build_linkedin_personal(brand,display,serif,tech):
    theme=brand["theme"]; identity=brand["identity"]; w,h=1584,396; image=gradient(w,h,theme); draw=ImageDraw.Draw(image)
    gold=rgb(theme["gold"]); gold_hi=rgb(theme["goldHighlight"]); ivory=rgb(theme["ivory"]); muted=rgb(theme["muted"]); x=440
    draw_text(draw,(x,86),identity["eyebrow"],fit_font(tech,identity["eyebrow"],18,650),gold)
    draw_text(draw,(x,166),identity["name"].upper(),fit_font(display,identity["name"].upper(),48,740),ivory)
    role="BUSINESS SYSTEMS ARCHITECT · FULL-STACK AI DEVELOPER"; draw_text(draw,(x,220),role,fit_font(serif,role,20,760),muted)
    draw.line((x,260,x+650,260),fill=(*gold,110),width=2)
    domains=" · ".join(identity["domains"]); draw_text(draw,(x,306),domains,fit_font(tech,domains,15,760),gold_hi)
    image.alpha_composite(orbit_layer(330,theme,0,"R",display),(1220,32)); return image

def build_linkedin_business(brand,display,serif,tech):
    theme=brand["theme"]; identity=brand["identity"]; w,h=4200,700; image=gradient(w,h,theme); draw=ImageDraw.Draw(image)
    gold=rgb(theme["gold"]); gold_hi=rgb(theme["goldHighlight"]); ivory=rgb(theme["ivory"]); muted=rgb(theme["muted"]); x=1320
    draw_text(draw,(x,170),identity["name"].upper(),fit_font(tech,identity["name"].upper(),31,1350),gold)
    draw_text(draw,(x,340),"BUSINESS SYSTEMS",fit_font(display,"BUSINESS SYSTEMS",108,1700),ivory)
    sub="Finance · Inventory · Operations Intelligence"; draw_text(draw,(x,440),sub,fit_font(serif,sub,42,1750),muted)
    draw.line((x,500,x+1650,500),fill=(*gold,110),width=3)
    line="ARCHITECTURE · AUTHORITY · EVIDENCE · DECISION"; draw_text(draw,(x,570),line,fit_font(tech,line,27,1700),gold_hi)
    image.alpha_composite(orbit_layer(560,theme,0,"R",display),(3450,65)); return image

def build_google(brand,display,serif,tech):
    theme=brand["theme"]; identity=brand["identity"]; w,h=1024,576; image=gradient(w,h,theme); draw=ImageDraw.Draw(image)
    gold=rgb(theme["gold"]); gold_hi=rgb(theme["goldHighlight"]); ivory=rgb(theme["ivory"]); muted=rgb(theme["muted"]); x=65
    draw_text(draw,(x,105),identity["eyebrow"],fit_font(tech,identity["eyebrow"],16,560),gold)
    draw_text(draw,(x,215),identity["name"].upper(),fit_font(display,identity["name"].upper(),54,630),ivory)
    draw_text(draw,(x,285),"FINANCE · INVENTORY · DATA · AI",fit_font(tech,"FINANCE · INVENTORY · DATA · AI",18,620),gold_hi)
    line="Operational intelligence for real business decisions."; draw_text(draw,(x,355),line,fit_font(serif,line,23,620),muted)
    image.alpha_composite(orbit_layer(390,theme,0,"R",display),(640,80)); return image

def build_instagram(brand,display,serif,tech):
    theme=brand["theme"]; identity=brand["identity"]; w,h=1080,1350; image=gradient(w,h,theme); draw=ImageDraw.Draw(image)
    gold=rgb(theme["gold"]); gold_hi=rgb(theme["goldHighlight"]); ivory=rgb(theme["ivory"]); muted=rgb(theme["muted"])
    image.alpha_composite(orbit_layer(650,theme,0,"R",display),(215,95))
    draw_text(draw,(540,820),"BUSINESS LOGIC,",fit_font(display,"BUSINESS LOGIC,",70,900),ivory,anchor="ma")
    draw_text(draw,(540,910),"MADE OPERATIONAL.",fit_font(display,"MADE OPERATIONAL.",70,900),gold_hi,anchor="ma")
    draw.line((230,980,850,980),fill=(*gold,110),width=3)
    line="FINANCE · INVENTORY · AI · INTERACTIVE PRODUCTS"; draw_text(draw,(540,1045),line,fit_font(tech,line,18,820),muted,anchor="ma")
    draw_text(draw,(540,1170),identity["name"].upper(),fit_font(serif,identity["name"].upper(),28,820),gold_hi,anchor="ma"); return image

def build_readme(brand,systems):
    identity=brand["identity"]; hero="./assets/generated/github/hero-motion.gif" if brand["motion"]["enabled"] else "./assets/generated/github/hero-dark.png"
    rows=[]
    for i in range(0,len(systems),2):
        cells=[]
        for system in systems[i:i+2]:
            card=f'<img alt="{system["title"]}" src="./assets/generated/projects/{system["id"]}.png" width="100%">'
            if system.get("url"): card=f'<a href="{system["url"]}">{card}</a>'
            cells.append("<td width=\"50%\">\n"+card+"\n<br>\n<sub>"+system["description"]+"</sub>\n</td>")
        if len(cells)==1: cells.append('<td width="50%"></td>')
        rows.append("<tr>\n"+"\n".join(cells)+"\n</tr>")
    table="<table>\n"+"\n".join(rows)+"\n</table>"
    return f'''<img alt="{identity["name"]}" src="{hero}" width="100%">

<p align="center"><strong>Business Systems Architect · Full-Stack AI Developer · Operations Intelligence Builder</strong></p>

<p align="center">{identity["tagline"]}</p>

<p align="center">
  <a href="{brand["links"]["portfolio"]}">Portfolio</a> ·
  <a href="{brand["links"]["repositories"]}">Repositories</a> ·
  {identity["location"]}
</p>

<br>

<p align="center"><img alt="Frontend to backend architecture boundary" src="./assets/generated/github/architecture-boundary.png" width="100%"></p>

## Selected systems

{table}

## Add another system

```bash
./brandctl add-system "CASTOR" "FINANCIAL INTELLIGENCE AND UNIT ECONOMICS" "https://github.com/Rodolfopr92/castor" "C"
./brandctl publish "Add Castor"
```

## Current direction

I am converting private architectural work into focused commercial products for finance, inventory, data migration, and security while continuing development of **The Quiet Ledger**.
'''

def build_all(animate=False):
    brand=read_json(CONFIG/"brand.json"); systems=read_json(CONFIG/"systems.json"); fonts=brand["fonts"]
    display=resolve_font("DISPLAY_FONT_PATH","DISPLAY_FONT_FAMILY",fonts["displayFamilies"])
    serif=resolve_font("SERIF_FONT_PATH","SERIF_FONT_FAMILY",fonts["serifFamilies"])
    tech=resolve_font("TECH_FONT_PATH","TECH_FONT_FAMILY",fonts["technicalFamilies"])
    print(f"Display: {display}\nSerif:   {serif}\nTech:    {tech}")
    for path in [OUT/"github",OUT/"projects",OUT/"social/linkedin-personal",OUT/"social/linkedin-business",OUT/"social/instagram",OUT/"social/google-business"]: path.mkdir(parents=True,exist_ok=True)
    save_full_bleed(build_hero(brand,display,serif,tech),OUT/"github/hero-dark.png")
    save_full_bleed(build_hero(brand,display,serif,tech,light=True),OUT/"github/hero-light.png")
    save_full_bleed(build_architecture(brand,serif,tech),OUT/"github/architecture-boundary.png")
    for system in systems: save_full_bleed(build_project_card(brand,system,display,tech),OUT/f"projects/{system['id']}.png")
    personal=build_linkedin_personal(brand,display,serif,tech)
    save_full_bleed(personal,OUT/"social/linkedin-personal/linkedin-personal-cover-1584x396.jpg"); save_full_bleed(personal,OUT/"social/linkedin-personal/linkedin-personal-cover-1584x396.png")
    business=build_linkedin_business(brand,display,serif,tech)
    save_full_bleed(business,OUT/"social/linkedin-business/linkedin-business-cover-4200x700.jpg"); save_full_bleed(business,OUT/"social/linkedin-business/linkedin-business-cover-4200x700.png")
    google=build_google(brand,display,serif,tech)
    save_full_bleed(google,OUT/"social/google-business/google-business-cover-1024x576.jpg"); save_full_bleed(google,OUT/"social/google-business/google-business-cover-1024x576.png")
    save_full_bleed(build_instagram(brand,display,serif,tech),OUT/"social/instagram/instagram-feed-1080x1350.png")
    if animate or brand["motion"]["enabled"]:
        frames=[]; count=int(brand["motion"]["frames"])
        for i in range(count):
            frame=build_hero(brand,display,serif,tech,angle=i*(360/count)).resize((1200,430),Image.Resampling.LANCZOS)
            frames.append(frame.convert("P",palette=Image.Palette.ADAPTIVE,colors=128))
        frames[0].save(OUT/"github/hero-motion.gif",save_all=True,append_images=frames[1:],duration=int(brand["motion"]["durationMs"]),loop=0,optimize=True,disposal=2)
    ROOT.joinpath("README.md").write_text(build_readme(brand,systems),encoding="utf-8")
    print("Brand build complete.")

if __name__=="__main__": build_all(animate="--animate" in os.sys.argv)
