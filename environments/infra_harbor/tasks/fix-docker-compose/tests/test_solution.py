import unittest
import yaml
import os


COMPOSE_FILE = "/infra/docker-compose.yml"


class ComposeFileTestCase(unittest.TestCase):
    """Tests that the compose file is valid and has required top-level keys."""

    def setUp(self):
        with open(COMPOSE_FILE, "r") as f:
            self.compose = yaml.safe_load(f)

    def test_file_is_valid_yaml(self):
        """The compose file should be valid YAML."""
        self.assertIsInstance(self.compose, dict)

    def test_has_version_field(self):
        """The compose file should retain the version field."""
        self.assertIn("version", self.compose)

    def test_has_services_key(self):
        """The compose file should have a services key."""
        self.assertIn("services", self.compose)


class WebServiceTestCase(unittest.TestCase):
    """Tests for the web service configuration."""

    def setUp(self):
        with open(COMPOSE_FILE, "r") as f:
            self.compose = yaml.safe_load(f)
        self.web = self.compose["services"]["web"]

    def test_port_mapping_is_correct(self):
        """Web service should map port 8080:5000."""
        ports = [str(p) for p in self.web.get("ports", [])]
        self.assertIn("8080:5000", ports)

    def test_port_8081_not_present(self):
        """Web service should NOT have port 8081 mapping."""
        ports = [str(p) for p in self.web.get("ports", [])]
        self.assertNotIn("8081:5000", ports)

    def test_has_redis_url_env(self):
        """Web service should have REDIS_URL environment variable."""
        env = self.web.get("environment", {})
        if isinstance(env, list):
            env_keys = [e.split("=")[0] for e in env]
            self.assertIn("REDIS_URL", env_keys)
        else:
            self.assertIn("REDIS_URL", env)

    def test_redis_url_value(self):
        """Web service REDIS_URL should point to redis://redis:6379/0."""
        env = self.web.get("environment", {})
        if isinstance(env, list):
            env_dict = dict(e.split("=", 1) for e in env)
            self.assertEqual(env_dict["REDIS_URL"], "redis://redis:6379/0")
        else:
            self.assertEqual(env["REDIS_URL"], "redis://redis:6379/0")

    def test_depends_on_postgres_with_condition(self):
        """Web service should depend on postgres with service_healthy condition."""
        depends = self.web.get("depends_on", {})
        self.assertIsInstance(depends, dict)
        self.assertIn("postgres", depends)
        self.assertEqual(depends["postgres"]["condition"], "service_healthy")

    def test_depends_on_redis(self):
        """Web service should depend on redis."""
        depends = self.web.get("depends_on", {})
        self.assertIsInstance(depends, dict)
        self.assertIn("redis", depends)

    def test_depends_on_redis_with_condition(self):
        """Web service should depend on redis with service_healthy condition."""
        depends = self.web.get("depends_on", {})
        self.assertIn("redis", depends)
        self.assertEqual(depends["redis"]["condition"], "service_healthy")


class PostgresServiceTestCase(unittest.TestCase):
    """Tests for the PostgreSQL service configuration."""

    def setUp(self):
        with open(COMPOSE_FILE, "r") as f:
            self.compose = yaml.safe_load(f)
        self.postgres = self.compose["services"]["postgres"]

    def test_image_is_postgres_16(self):
        """PostgreSQL service should use postgres:16 image."""
        self.assertEqual(self.postgres["image"], "postgres:16")

    def test_image_not_postgres_13(self):
        """PostgreSQL service should NOT use postgres:13 image."""
        self.assertNotEqual(self.postgres["image"], "postgres:13")

    def test_has_healthcheck(self):
        """PostgreSQL service should have a healthcheck defined."""
        self.assertIn("healthcheck", self.postgres)

    def test_healthcheck_uses_pg_isready(self):
        """PostgreSQL healthcheck should use pg_isready command."""
        hc = self.postgres["healthcheck"]
        test_cmd = hc.get("test", [])
        if isinstance(test_cmd, list):
            self.assertTrue(any("pg_isready" in str(part) for part in test_cmd))
        else:
            self.assertIn("pg_isready", str(test_cmd))

    def test_healthcheck_has_interval(self):
        """PostgreSQL healthcheck should have an interval setting."""
        hc = self.postgres["healthcheck"]
        self.assertIn("interval", hc)

    def test_healthcheck_has_timeout(self):
        """PostgreSQL healthcheck should have a timeout setting."""
        hc = self.postgres["healthcheck"]
        self.assertIn("timeout", hc)

    def test_healthcheck_has_retries(self):
        """PostgreSQL healthcheck should have a retries setting."""
        hc = self.postgres["healthcheck"]
        self.assertIn("retries", hc)

    def test_volume_mounted(self):
        """PostgreSQL service should have a volume mounted at /var/lib/postgresql/data."""
        volumes = self.postgres.get("volumes", [])
        volume_strings = [str(v) for v in volumes]
        self.assertTrue(
            any("/var/lib/postgresql/data" in v for v in volume_strings),
            f"Expected a volume mount at /var/lib/postgresql/data, got: {volume_strings}",
        )


class RedisServiceTestCase(unittest.TestCase):
    """Tests for the Redis service configuration."""

    def setUp(self):
        with open(COMPOSE_FILE, "r") as f:
            self.compose = yaml.safe_load(f)
        self.services = self.compose.get("services", {})

    def test_redis_service_exists(self):
        """Redis service should exist in the compose file."""
        self.assertIn("redis", self.services)

    def test_redis_image(self):
        """Redis service should use redis:7-alpine image."""
        redis = self.services["redis"]
        self.assertEqual(redis["image"], "redis:7-alpine")

    def test_redis_has_healthcheck(self):
        """Redis service should have a healthcheck defined."""
        redis = self.services["redis"]
        self.assertIn("healthcheck", redis)

    def test_redis_ports(self):
        """Redis service should expose port 6379:6379."""
        redis = self.services["redis"]
        ports = [str(p) for p in redis.get("ports", [])]
        self.assertIn("6379:6379", ports)


class WorkerServiceTestCase(unittest.TestCase):
    """Tests for the worker service configuration."""

    def setUp(self):
        with open(COMPOSE_FILE, "r") as f:
            self.compose = yaml.safe_load(f)
        self.worker = self.compose["services"]["worker"]

    def test_has_redis_url_env(self):
        """Worker service should have REDIS_URL environment variable."""
        env = self.worker.get("environment", {})
        if isinstance(env, list):
            env_keys = [e.split("=")[0] for e in env]
            self.assertIn("REDIS_URL", env_keys)
        else:
            self.assertIn("REDIS_URL", env)

    def test_redis_url_value(self):
        """Worker service REDIS_URL should point to redis://redis:6379/0."""
        env = self.worker.get("environment", {})
        if isinstance(env, list):
            env_dict = dict(e.split("=", 1) for e in env)
            self.assertEqual(env_dict["REDIS_URL"], "redis://redis:6379/0")
        else:
            self.assertEqual(env["REDIS_URL"], "redis://redis:6379/0")

    def test_depends_on_includes_redis(self):
        """Worker service should depend on redis."""
        depends = self.worker.get("depends_on", {})
        if isinstance(depends, list):
            self.assertIn("redis", depends)
        else:
            self.assertIn("redis", depends)


class VolumeTestCase(unittest.TestCase):
    """Tests for volume configuration."""

    def setUp(self):
        with open(COMPOSE_FILE, "r") as f:
            self.compose = yaml.safe_load(f)

    def test_top_level_volumes_has_postgres_data(self):
        """Top-level volumes should include postgres_data."""
        volumes = self.compose.get("volumes", {})
        self.assertIn("postgres_data", volumes)

    def test_postgres_uses_named_volume(self):
        """PostgreSQL service should use the postgres_data named volume."""
        postgres = self.compose["services"]["postgres"]
        volumes = [str(v) for v in postgres.get("volumes", [])]
        self.assertTrue(
            any("postgres_data" in v for v in volumes),
            f"Expected postgres_data volume in postgres service, got: {volumes}",
        )


class NginxPreservedTestCase(unittest.TestCase):
    """Tests that the nginx service is preserved."""

    def setUp(self):
        with open(COMPOSE_FILE, "r") as f:
            self.compose = yaml.safe_load(f)
        self.services = self.compose.get("services", {})

    def test_nginx_service_exists(self):
        """Nginx service should still exist in the compose file."""
        self.assertIn("nginx", self.services)

    def test_nginx_depends_on_web(self):
        """Nginx service should still depend on the web service."""
        nginx = self.services["nginx"]
        depends = nginx.get("depends_on", [])
        if isinstance(depends, list):
            self.assertIn("web", depends)
        else:
            self.assertIn("web", depends)


if __name__ == "__main__":
    unittest.main()
