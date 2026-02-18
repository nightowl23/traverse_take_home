import subprocess
import unittest


NGINX_CONF = "/infra/nginx/nginx.conf"
DEFAULT_CONF = "/infra/nginx/conf.d/default.conf"


def read_file(path):
    with open(path, "r") as f:
        return f.read()


class NginxSyntaxTestCase(unittest.TestCase):
    """Validate that the nginx configuration passes syntax check."""

    def test_nginx_syntax_is_valid(self):
        # Add dummy host entry so nginx can resolve the upstream "web" hostname
        with open("/etc/hosts", "a") as f:
            f.write("127.0.0.1 web\n")
        result = subprocess.run(
            ["nginx", "-t", "-c", NGINX_CONF],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"nginx -t failed:\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )


class UpstreamTestCase(unittest.TestCase):
    """Check that the upstream block points to the correct port."""

    def setUp(self):
        self.content = read_file(NGINX_CONF)

    def test_upstream_has_correct_port(self):
        self.assertIn("server web:5000", self.content)

    def test_upstream_does_not_have_wrong_port(self):
        self.assertNotIn("server web:8000", self.content)

    def test_upstream_block_exists(self):
        self.assertIn("upstream webapp", self.content)


class ProxyHeadersTestCase(unittest.TestCase):
    """Check that all four proxy_set_header directives are present in default.conf."""

    def setUp(self):
        self.content = read_file(DEFAULT_CONF)

    def test_proxy_set_header_host(self):
        self.assertIn("proxy_set_header Host", self.content)

    def test_proxy_set_header_x_real_ip(self):
        self.assertIn("proxy_set_header X-Real-IP", self.content)

    def test_proxy_set_header_x_forwarded_for(self):
        self.assertIn("proxy_set_header X-Forwarded-For", self.content)

    def test_proxy_set_header_x_forwarded_proto(self):
        self.assertIn("proxy_set_header X-Forwarded-Proto", self.content)


class RateLimitTestCase(unittest.TestCase):
    """Check that rate limiting is configured in both files."""

    def test_limit_req_zone_in_nginx_conf(self):
        content = read_file(NGINX_CONF)
        self.assertIn("limit_req_zone", content)

    def test_limit_req_zone_uses_binary_remote_addr(self):
        content = read_file(NGINX_CONF)
        self.assertIn("$binary_remote_addr", content)

    def test_limit_req_in_default_conf(self):
        content = read_file(DEFAULT_CONF)
        self.assertIn("limit_req zone=one", content)


class StaticFilesTestCase(unittest.TestCase):
    """Check that the /static/ location is configured correctly."""

    def setUp(self):
        self.content = read_file(DEFAULT_CONF)

    def test_static_location_exists(self):
        self.assertIn("location /static/", self.content)

    def test_static_expires_30d(self):
        self.assertIn("expires 30d", self.content)

    def test_static_cache_control_header(self):
        self.assertIn('add_header Cache-Control "public"', self.content)


class GzipTestCase(unittest.TestCase):
    """Check that gzip compression is enabled in nginx.conf."""

    def setUp(self):
        self.content = read_file(NGINX_CONF)

    def test_gzip_on(self):
        self.assertIn("gzip on", self.content)

    def test_gzip_types(self):
        self.assertIn("gzip_types", self.content)

    def test_gzip_min_length(self):
        self.assertIn("gzip_min_length", self.content)


class HealthCheckTestCase(unittest.TestCase):
    """Check that the /health endpoint is configured."""

    def setUp(self):
        self.content = read_file(DEFAULT_CONF)

    def test_health_location_exists(self):
        self.assertIn("location /health", self.content)

    def test_health_returns_200(self):
        self.assertIn("return 200", self.content)


class ApiLocationTestCase(unittest.TestCase):
    """Check that the /api/ location is configured."""

    def setUp(self):
        self.content = read_file(DEFAULT_CONF)

    def test_api_location_exists(self):
        self.assertIn("location /api/", self.content)

    def test_api_proxy_pass(self):
        self.assertIn("proxy_pass http://webapp", self.content)


class PreservationTestCase(unittest.TestCase):
    """Check that required directives and blocks are preserved."""

    def setUp(self):
        self.content = read_file(NGINX_CONF)

    def test_worker_processes_auto(self):
        self.assertIn("worker_processes auto", self.content)

    def test_events_block_exists(self):
        self.assertIn("events", self.content)

    def test_upstream_block_preserved(self):
        self.assertIn("upstream webapp", self.content)


if __name__ == "__main__":
    unittest.main()
