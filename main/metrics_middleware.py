from prometheus_client import Counter

http_responses_total = Counter(
    "mycube_http_responses_total",
    "Total HTTP responses produced by Django app",
    ["status_class", "status_code"],
)


class PrometheusHttpStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            self._observe_status(response.status_code)
            return response
        except Exception:
            self._observe_status(500)
            raise

    @staticmethod
    def _observe_status(status_code):
        code = int(status_code)
        status_class = f"{code // 100}xx"
        http_responses_total.labels(status_class=status_class, status_code=str(code)).inc()
