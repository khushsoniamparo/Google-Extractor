import json
import re

def parse_html_for_places(html_content):
    matches = re.findall(r'window\.APP_INITIALIZATION_STATE=\[\[\[(.*?)\]\]\];', html_content)
    if not matches:
        print("No matches")
        return []
    
    json_str = "[[[" + matches[0] + "]]]"
    try:
        data = json.loads(json_str)
        print("JSON loaded successfully.")
    except Exception as e:
        print(f"JSON load failed: {e}")
        return []

    places = []
    
    def extract_place(node):
        try:
            # Most Gmap place nodes are long lists
            if isinstance(node, list) and len(node) > 10:
                # Look for place_id pattern
                place_id = None
                name = None
                
                for i, item in enumerate(node):
                    if isinstance(item, str) and item.startswith("ChI") and len(item) > 20:
                        place_id = item
                    elif isinstance(item, str) and len(item) > 2 and " " in item:
                        # might be name
                        pass

                if isinstance(node[14], list) and len(node[14]) > 5:
                    info = node[14]
                    if isinstance(info[11], str):
                        name = info[11]
                    
                    if name:
                        places.append({"name": name, "raw_len": len(node)})
        except Exception:
            pass

        if isinstance(node, list):
            for item in node:
                extract_place(item)
        elif isinstance(node, dict):
            for val in node.values():
                extract_place(val)
                
    extract_place(data)
    return places

with open("output2_raw.txt", "r", encoding="utf-8") as f:
    text = f.read()
    
found = parse_html_for_places(text)
print(f"Found {len(found)} places")
if found:
    print(found[:3])
