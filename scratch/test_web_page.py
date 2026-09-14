import urllib.request

req = urllib.request.Request('http://localhost:8069/hudson_kitchen_display/web?display_id=1')
try:
    with urllib.request.urlopen(req) as resp:
        print("Status:", resp.status)
        content = resp.read().decode('utf-8')
        print("Length:", len(content))
        print("First 500 chars:")
        print(content[:500])
        print("...")
        print("Last 500 chars:")
        print(content[-500:])
except Exception as e:
    print("Error:", e)
