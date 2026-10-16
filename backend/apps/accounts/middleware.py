class CompanyTenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            request.company = user.company
            request.company_id = user.company_id
        else:
            request.company = None
            request.company_id = None
        return self.get_response(request)
