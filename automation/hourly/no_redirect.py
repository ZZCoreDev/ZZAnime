"""11/11/2026 quinta revisión S-05: opener for requests that carry a key (GitHub, Cloudflare, collector). A redirect is
never followed (urllib would resend Authorization to the new host): it raises HTTPError with the 3xx code instead."""
import urllib.request
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k):return None
NO_REDIRECT=urllib.request.build_opener(_NoRedirect())
