//! Canonical, integer-only IDART1 SVG renderer. No URLs, scripts, fonts or clock.
use std::fmt::Write;

pub const MAX_BYTES: usize = 262144;
pub const MAX_SVG: usize = 2_000_000;
#[derive(Debug)]
pub struct Scene {
    pub width: u32,
    pub height: u32,
    pub top: String,
    pub bottom: String,
    pub period: u32,
    pub pulse: u32,
    pub activity: Vec<u8>,
    pub style: u32,
    pub strength: u32,
    pub direction: u32,
    pub route_period: u32,
    pub shapes: Vec<Shape>,
}
#[derive(Debug)]
pub struct Shape {
    pub kind: u32,
    pub color: String,
    pub alpha: u32,
    pub flags: u32,
    pub phase: u32,
    pub weight: u32,
    pub stroke: Option<String>,
    pub size: u32,
    pub points: Vec<(u32, u32)>,
}
struct Reader<'a> {
    data: &'a [u8],
    pos: usize,
}
impl Reader<'_> {
    fn bytes(&mut self, n: usize) -> Result<&[u8], &'static str> {
        let value = self
            .data
            .get(self.pos..self.pos + n)
            .ok_or("Truncated recipe")?;
        self.pos += n;
        Ok(value)
    }
    fn number(&mut self, n: usize) -> Result<u32, &'static str> {
        Ok(self.bytes(n)?.iter().fold(0, |a, b| (a << 8) | *b as u32))
    }
    fn color(&mut self) -> Result<String, &'static str> {
        let b = self.bytes(3)?;
        Ok(format!("#{:02X}{:02X}{:02X}", b[0], b[1], b[2]))
    }
}
pub fn decode(data: &[u8]) -> Result<Scene, &'static str> {
    if data.len() > MAX_BYTES {
        return Err("Recipe budget exceeded");
    }
    let mut r = Reader { data, pos: 0 };
    if r.bytes(6)? != b"IDART1" {
        return Err("Unknown format");
    }
    let width = r.number(2)?;
    let height = r.number(2)?;
    if !(64..=2048).contains(&width) || !(64..=2048).contains(&height) {
        return Err("Invalid canvas");
    }
    let top = r.color()?;
    let bottom = r.color()?;
    let count = r.number(2)?;
    let period = r.number(2)?;
    let pulse = r.number(2)?;
    if !(1..=8192).contains(&count)
        || !(1000..=60000).contains(&period)
        || !(80..=1000).contains(&pulse)
    {
        return Err("Invalid scene budget");
    }
    let activity = r.bytes(48)?.to_vec();
    let style = r.number(1)?;
    let strength = r.number(2)?;
    let direction = r.number(1)?;
    let route_period = r.number(2)?;
    if style > 17 || strength > 1000 || direction > 1 || !(1000..=60000).contains(&route_period) {
        return Err("Invalid motion");
    }
    let mut shapes = Vec::new();
    let mut vertices = 0;
    for _ in 0..count {
        let kind = r.number(1)?;
        let color = r.color()?;
        let alpha = r.number(1)?;
        let flags = r.number(1)?;
        let phase = r.number(2)?;
        if kind > 3 || flags > 31 || flags & 16 != 0 && !matches!(kind, 1 | 2) {
            return Err("Unknown shape");
        }
        let weight = if flags & 8 != 0 { r.number(1)? } else { 0 };
        let stroke = if flags & 1 != 0 {
            Some(r.color()?)
        } else {
            None
        };
        let size = r.number(3)?;
        if size == 0 || size > 100000 {
            return Err("Invalid stroke/radius");
        }
        let count = if kind == 0 { 1 } else { r.number(2)? };
        if count == 0
            || count > 512
            || kind == 1 && count < 2
            || kind == 2 && count != 4
            || kind == 3 && count < 3
        {
            return Err("Invalid path");
        }
        vertices += count;
        if vertices > 32768 {
            return Err("Vertex budget exceeded");
        }
        let mut points = Vec::new();
        for _ in 0..count {
            let x = r.number(3)?;
            let y = r.number(3)?;
            if x > width * 1000 || y > height * 1000 {
                return Err("Point outside canvas");
            }
            points.push((x, y));
        }
        shapes.push(Shape {
            kind,
            color,
            alpha,
            flags,
            phase,
            weight,
            stroke,
            size,
            points,
        });
    }
    if r.pos != data.len() {
        return Err("Trailing recipe bytes");
    }
    Ok(Scene {
        width,
        height,
        top,
        bottom,
        period,
        pulse,
        activity,
        style,
        strength,
        direction,
        route_period,
        shapes,
    })
}
pub fn decimal(n: u32, digits: u32) -> String {
    let base = 10u32.pow(digits);
    let rem = n % base;
    if rem == 0 {
        return (n / base).to_string();
    }
    format!("{}.{:0width$}", n / base, rem, width = digits as usize)
        .trim_end_matches('0')
        .to_string()
}
fn escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}
pub fn svg(scene: &Scene, title: &str, animated: bool) -> Result<String, &'static str> {
    let mut out=format!("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 {} {}\" role=\"img\"><title>{}</title><defs><linearGradient id=\"bg\" x2=\"0\" y2=\"1\"><stop stop-color=\"{}\"/><stop offset=\"1\" stop-color=\"{}\"/></linearGradient><filter id=\"glow\" x=\"-30%\" y=\"-30%\" width=\"160%\" height=\"160%\"><feGaussianBlur stdDeviation=\"1.8\"/><feMerge><feMergeNode/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter></defs><rect width=\"{}\" height=\"{}\" fill=\"url(#bg)\"/><g>",scene.width,scene.height,escape(title),scene.top,scene.bottom,scene.width,scene.height);
    if animated {
        let mut values: Vec<String> = scene
            .activity
            .iter()
            .map(|v| {
                decimal(
                    1000 - scene.strength / 3 + *v as u32 * scene.strength / 3 / 255,
                    3,
                )
            })
            .collect();
        values.push(values[0].clone());
        write!(out,"<animate attributeName=\"opacity\" values=\"{}\" dur=\"{}s\" repeatCount=\"indefinite\"/>",values.join(";"),decimal(scene.period,3)).unwrap();
        if matches!(scene.style / 3, 0 | 3 | 4) && scene.style % 3 != 1 {
            let angle = decimal(500 + scene.strength * 4, 3);
            let sign = if scene.direction == 0 { "-" } else { "" };
            write!(out,"<animateTransform attributeName=\"transform\" type=\"rotate\" values=\"0 {} {};{}{} {} {};0 {} {}\" dur=\"{}s\" repeatCount=\"indefinite\"/>",scene.width/2,scene.height/2,sign,angle,scene.width/2,scene.height/2,scene.width/2,scene.height/2,decimal(scene.period,3)).unwrap();
        }
        if scene.style / 3 == 5 {
            let amount = scene.strength / 35;
            write!(out,"<g transform=\"translate({} {})\"><g><animateTransform attributeName=\"transform\" type=\"scale\" values=\"1;{};1\" dur=\"{}s\" repeatCount=\"indefinite\"/><g transform=\"translate(-{} -{})\">",scene.width/2,scene.height/2,decimal(1000+amount,3),decimal(scene.period,3),scene.width/2,scene.height/2).unwrap();
        }
    }
    for shape in &scene.shapes {
        let alpha = decimal((shape.alpha * 10000 + 127) / 255, 4);
        let glow = if shape.flags & 2 != 0 {
            " filter=\"url(#glow)\""
        } else {
            ""
        };
        let size = decimal(shape.size, 3);
        let tag = match shape.kind {
            0 => "circle",
            1 => "polyline",
            2 => "path",
            _ => "polygon",
        };
        write!(out, "<{tag} opacity=\"{alpha}\"{glow}").unwrap();
        if shape.kind == 0 {
            write!(
                out,
                " cx=\"{}\" cy=\"{}\" r=\"{}\" fill=\"{}\"",
                decimal(shape.points[0].0, 3),
                decimal(shape.points[0].1, 3),
                size,
                shape.color
            )
            .unwrap();
        } else {
            if shape.kind == 2 {
                let p = &shape.points;
                write!(
                    out,
                    " d=\"M{},{} C{},{} {},{} {},{}\"",
                    decimal(p[0].0, 3),
                    decimal(p[0].1, 3),
                    decimal(p[1].0, 3),
                    decimal(p[1].1, 3),
                    decimal(p[2].0, 3),
                    decimal(p[2].1, 3),
                    decimal(p[3].0, 3),
                    decimal(p[3].1, 3)
                )
                .unwrap();
            } else {
                out.push_str(" points=\"");
                for (i, (x, y)) in shape.points.iter().enumerate() {
                    if i > 0 {
                        out.push(' ')
                    }
                    write!(out, "{},{}", decimal(*x, 3), decimal(*y, 3)).unwrap();
                }
                out.push('"');
            }
            if shape.kind == 3 {
                write!(
                    out,
                    " fill=\"{}\" stroke=\"{}\" stroke-width=\"{}\"",
                    shape.color,
                    shape.stroke.as_ref().unwrap_or(&shape.color),
                    size
                )
                .unwrap();
            } else {
                write!(
                    out,
                    " fill=\"none\" stroke=\"{}\" stroke-width=\"{}\"",
                    shape.color, size
                )
                .unwrap();
            }
        }
        out.push('>');
        if animated && scene.style / 3 == 1 && shape.flags & 16 != 0 {
            write!(out,"<animate attributeName=\"stroke-dasharray\" values=\"0 4000;4000 0;4000 0;0 4000\" keyTimes=\"0;0.65;0.98;1\" dur=\"{}s\" begin=\"-{}s\" repeatCount=\"indefinite\"/>",decimal(scene.period,3),decimal(shape.phase*scene.period/65535,3)).unwrap();
        }
        let facet = shape.kind == 3 && scene.style / 3 == 2;
        if animated && (shape.flags & 4 != 0 || facet) {
            let low = decimal(
                (shape.alpha * 10000 + 127) / 255 * (1000 - scene.strength / 2) / 1000,
                4,
            );
            let values = if scene.style % 3 == 1 {
                format!("{alpha};{low};{alpha}")
            } else {
                format!("{low};{alpha};{low}")
            };
            write!(out,"<animate attributeName=\"opacity\" values=\"{}\" dur=\"{}s\" begin=\"-{}s\" repeatCount=\"indefinite\"/>",values,decimal(1_000_000/scene.pulse*if scene.style%3==2 {2} else {1},3),decimal(shape.phase*scene.period/65535,3)).unwrap();
        }
        if animated && shape.flags & 8 != 0 {
            // Thin moving highlights retain the same fixed route geometry.
            let rate = scene.route_period * 255 / (255 + shape.weight * 2);
            write!(out,"<animate attributeName=\"stroke-dasharray\" values=\"2 14;6 10;2 14\" dur=\"{}s\" repeatCount=\"indefinite\"/><animate attributeName=\"stroke-dashoffset\" from=\"0\" to=\"{}16\" dur=\"{}s\" repeatCount=\"indefinite\"/>",decimal(rate,3),if scene.direction==0 {"-"} else {""},decimal(rate,3)).unwrap();
        }
        write!(out, "</{tag}>").unwrap();
        if out.len() > MAX_SVG {
            return Err("SVG budget exceeded");
        }
    }
    if animated && scene.style / 3 == 5 {
        out.push_str("</g></g></g>")
    }
    out.push_str("</g></svg>");
    Ok(out)
}
