import os
import xml.etree.ElementTree as ET
import math

def generate_xmp_sidecar(dng_path, score, is_promising, critique_bullets, style, photographers):
    """
    Generates an Adobe-compliant XMP sidecar file for a given DNG file.
    Maps a 1-10 score to a 1-5 star rating.
    Injects critique bullets into the 'Caption' (dc:description) field.
    Injects keywords into the 'Keywords' (dc:subject) field.
    """
    # Calculate star rating (1-5) from score (1-10)
    rating = max(1, min(5, math.ceil(score / 2.0)))
    
    # Format the critique bullets into a single string for the description
    description_text = "AI Critique:\n- " + "\n- ".join(critique_bullets)
    if photographers:
        description_text += f"\n\nStyle Reference: {', '.join(photographers)}"
    
    # Prepare keywords
    keywords = ["AI Reviewed"]
    if is_promising:
        keywords.append("Promising")
    if style and style != "Any":
        keywords.append(style)
        
    # Construct the XML structure
    xmpmeta = ET.Element('x:xmpmeta', {'xmlns:x': 'adobe:ns:meta/', 'x:xmptk': 'PhotoReviewAgent 1.0'})
    rdf = ET.SubElement(xmpmeta, 'rdf:RDF', {'xmlns:rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'})
    desc = ET.SubElement(rdf, 'rdf:Description', {
        'rdf:about': '',
        'xmlns:xmp': 'http://ns.adobe.com/xap/1.0/',
        'xmlns:dc': 'http://purl.org/dc/elements/1.1/'
    })
    
    # Add Rating
    rating_el = ET.SubElement(desc, 'xmp:Rating')
    rating_el.text = str(rating)
    
    # Add Description (Caption)
    dc_description = ET.SubElement(desc, 'dc:description')
    alt = ET.SubElement(dc_description, 'rdf:Alt')
    li_desc = ET.SubElement(alt, 'rdf:li', {'xml:lang': 'x-default'})
    li_desc.text = description_text
    
    # Add Keywords
    dc_subject = ET.SubElement(desc, 'dc:subject')
    bag = ET.SubElement(dc_subject, 'rdf:Bag')
    for kw in keywords:
        li_kw = ET.SubElement(bag, 'rdf:li')
        li_kw.text = kw
        
    # Generate the XML string
    # Add xml declaration manually for exact match to XMP standard
    xml_str = '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
    xml_str += ET.tostring(xmpmeta, encoding='unicode', xml_declaration=False)
    xml_str += '\n<?xpacket end="w"?>'
    
    # Write to file
    base_name = os.path.splitext(dng_path)[0]
    xmp_path = f"{base_name}.xmp"
    
    with open(xmp_path, 'w', encoding='utf-8') as f:
        f.write(xml_str)
        
    return xmp_path

def read_xmp_sidecar(xmp_path):
    """
    Reads an existing XMP sidecar file and attempts to extract:
    - score (mapped back from star rating)
    - is_promising (whether "Promising" keyword is present)
    - critique_bullets (extracted from description text)
    Returns a dictionary matching the analysis format, or None if it cannot be read/parsed.
    """
    if not os.path.exists(xmp_path):
        return None
        
    try:
        with open(xmp_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Clean processing instructions so standard xml parser does not fail
        lines = []
        for line in content.splitlines():
            if not (line.strip().startswith('<?xpacket') or line.strip().endswith('?>')):
                lines.append(line)
        cleaned_content = "\n".join(lines)
        
        root = ET.fromstring(cleaned_content)
        
        # XML Namespace mappings
        ns = {
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'xmp': 'http://ns.adobe.com/xap/1.0/',
            'dc': 'http://purl.org/dc/elements/1.1/'
        }
        
        desc = root.find('.//rdf:Description', ns)
        if desc is None:
            return None
            
        # Get Rating (1-5 stars)
        rating_el = desc.find('xmp:Rating', ns)
        rating = int(rating_el.text) if rating_el is not None and rating_el.text else 0
        score = rating * 2
        
        # Get Description (AI Critique)
        critique_bullets = []
        li_desc = desc.find('.//dc:description/rdf:Alt/rdf:li', ns)
        if li_desc is not None and li_desc.text:
            text = li_desc.text
            if "AI Critique:\n-" in text:
                parts = text.split("AI Critique:\n-")
                if len(parts) > 1:
                    bullet_text = parts[1].split("\n\nStyle Reference:")[0]
                    for bullet in bullet_text.split("\n- "):
                        bullet = bullet.strip()
                        if bullet:
                            critique_bullets.append(bullet)
                            
        if not critique_bullets and li_desc is not None and li_desc.text:
            critique_bullets = [li_desc.text.strip()]
            
        # Get Keywords to see if "Promising" is present
        is_promising = False
        bag = desc.find('.//dc:subject/rdf:Bag', ns)
        if bag is not None:
            for li in bag.findall('rdf:li', ns):
                if li.text == "Promising":
                    is_promising = True
                    
        # Check if the parsed review is actually an error/failure
        if score == 0 or any("error" in b.lower() for b in critique_bullets):
            return None
            
        # Score adjustment alignment
        if is_promising and score < 7:
            score = 7
        elif not is_promising and score >= 7:
            score = 6
            
        return {
            "score": score,
            "is_promising": is_promising,
            "critique_bullets": critique_bullets
        }
    except Exception as e:
        print(f"Error reading XMP sidecar {xmp_path}: {e}")
        return None

if __name__ == "__main__":
    # Test
    xmp_file = generate_xmp_sidecar("test.dng", 8, True, ["Great composition", "Good colors"], "Color", ["Alex Webb"])
    print("Parsed back:", read_xmp_sidecar(xmp_file))

