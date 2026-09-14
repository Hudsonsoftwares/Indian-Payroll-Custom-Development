import urllib.request
import http.cookiejar

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# Visit with db parameter to set session db
opener.open('http://localhost:8069/web/login?db=RevisedPayroll')
r2 = opener.open('http://localhost:8069/hudson_kitchen_display/order_status?display_id=1')
html = r2.read().decode('utf-8')
print('Title found:', '<title>Order Tracking</title>' in html)
print('Ready section:', 'pos-tracking-title">Ready</h1>' in html)
print('Almost there section:', 'pos-tracking-title">Almost there</h1>' in html)
print('Odoo branding:', 'pos-tracking-logo">odoo</div>' in html)
print('Length:', len(html))
