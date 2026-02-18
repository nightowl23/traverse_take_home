import os
import unittest

import yaml

CI_YML_PATH = "/infra/.github/workflows/ci.yml"


def load_ci_yml():
    with open(CI_YML_PATH, "r") as f:
        return yaml.safe_load(f)


class CiFileExistsTestCase(unittest.TestCase):
    def test_ci_file_exists(self):
        self.assertTrue(os.path.isfile(CI_YML_PATH), f"{CI_YML_PATH} does not exist")

    def test_ci_file_is_valid_yaml(self):
        data = load_ci_yml()
        self.assertIsInstance(data, dict, "ci.yml did not parse as a YAML mapping")


class TriggersTestCase(unittest.TestCase):
    def setUp(self):
        self.data = load_ci_yml()

    def test_has_on_key(self):
        self.assertIn(True, [k == True or k == "on" or str(k) == "True" for k in self.data.keys()] if not any(str(k) == "on" for k in self.data.keys()) else [True],
                       "Workflow must have an 'on' trigger key")
        # yaml.safe_load parses bare 'on' as True key
        trigger = self.data.get(True) or self.data.get("on")
        self.assertIsNotNone(trigger, "Trigger configuration must not be None")

    def test_push_trigger_on_main(self):
        trigger = self.data.get(True) or self.data.get("on")
        self.assertIn("push", trigger, "Must have push trigger")
        branches = trigger["push"].get("branches", [])
        self.assertIn("main", branches, "push must trigger on main branch")

    def test_pull_request_trigger_on_main(self):
        trigger = self.data.get(True) or self.data.get("on")
        self.assertIn("pull_request", trigger, "Must have pull_request trigger")
        branches = trigger["pull_request"].get("branches", [])
        self.assertIn("main", branches, "pull_request must trigger on main branch")


class LintJobTestCase(unittest.TestCase):
    def setUp(self):
        self.data = load_ci_yml()
        self.jobs = self.data.get("jobs", {})
        self.lint = self.jobs.get("lint", {})

    def test_lint_job_exists(self):
        self.assertIn("lint", self.jobs, "lint job must exist")

    def test_lint_runs_on_ubuntu(self):
        self.assertEqual(self.lint.get("runs-on"), "ubuntu-latest")

    def test_lint_has_checkout_step(self):
        steps = self.lint.get("steps", [])
        checkout_steps = [s for s in steps if s.get("uses", "").startswith("actions/checkout")]
        self.assertGreater(len(checkout_steps), 0, "lint must have a checkout step")

    def test_lint_has_hadolint_web(self):
        steps = self.lint.get("steps", [])
        hadolint_web = [
            s for s in steps
            if "hadolint" in s.get("uses", "")
            and s.get("with", {}).get("dockerfile") == "Dockerfile.web"
        ]
        self.assertGreater(len(hadolint_web), 0, "lint must have hadolint step for Dockerfile.web")

    def test_lint_has_hadolint_worker(self):
        steps = self.lint.get("steps", [])
        hadolint_worker = [
            s for s in steps
            if "hadolint" in s.get("uses", "")
            and s.get("with", {}).get("dockerfile") == "Dockerfile.worker"
        ]
        self.assertGreater(len(hadolint_worker), 0, "lint must have hadolint step for Dockerfile.worker")

    def test_lint_has_yamllint_step(self):
        steps = self.lint.get("steps", [])
        yamllint_steps = [s for s in steps if "yamllint" in s.get("run", "")]
        self.assertGreater(len(yamllint_steps), 0, "lint must have a yamllint step")


class TestJobTestCase(unittest.TestCase):
    def setUp(self):
        self.data = load_ci_yml()
        self.jobs = self.data.get("jobs", {})
        self.test_job = self.jobs.get("test", {})

    def test_test_job_exists(self):
        self.assertIn("test", self.jobs, "test job must exist")

    def test_test_runs_on_ubuntu(self):
        self.assertEqual(self.test_job.get("runs-on"), "ubuntu-latest")

    def test_test_needs_lint(self):
        needs = self.test_job.get("needs")
        if isinstance(needs, list):
            self.assertIn("lint", needs)
        else:
            self.assertEqual(needs, "lint")

    def test_test_has_checkout_step(self):
        steps = self.test_job.get("steps", [])
        checkout_steps = [s for s in steps if s.get("uses", "").startswith("actions/checkout")]
        self.assertGreater(len(checkout_steps), 0, "test must have a checkout step")

    def test_test_has_setup_python(self):
        steps = self.test_job.get("steps", [])
        setup_python = [s for s in steps if "setup-python" in s.get("uses", "")]
        self.assertGreater(len(setup_python), 0, "test must have setup-python step")

    def test_test_python_version_311(self):
        steps = self.test_job.get("steps", [])
        for s in steps:
            if "setup-python" in s.get("uses", ""):
                version = str(s.get("with", {}).get("python-version", ""))
                self.assertIn("3.11", version, "Python version must be 3.11")
                return
        self.fail("setup-python step not found")

    def test_test_has_install_dependencies(self):
        steps = self.test_job.get("steps", [])
        install_steps = [s for s in steps if "requirements.txt" in s.get("run", "")]
        self.assertGreater(len(install_steps), 0, "test must have install dependencies step")

    def test_test_has_run_tests_step(self):
        steps = self.test_job.get("steps", [])
        pytest_steps = [s for s in steps if "pytest" in s.get("run", "")]
        self.assertGreater(len(pytest_steps), 0, "test must have a pytest step")


class BuildAndPushJobTestCase(unittest.TestCase):
    def setUp(self):
        self.data = load_ci_yml()
        self.jobs = self.data.get("jobs", {})
        self.build = self.jobs.get("build-and-push", {})

    def test_build_job_exists(self):
        self.assertIn("build-and-push", self.jobs, "build-and-push job must exist")

    def test_build_runs_on_ubuntu(self):
        self.assertEqual(self.build.get("runs-on"), "ubuntu-latest")

    def test_build_needs_test(self):
        needs = self.build.get("needs")
        if isinstance(needs, list):
            self.assertIn("test", needs)
        else:
            self.assertEqual(needs, "test")

    def test_build_has_if_condition(self):
        condition = self.build.get("if", "")
        self.assertIn("refs/heads/main", condition, "build-and-push must have if condition with refs/heads/main")

    def test_build_has_checkout_step(self):
        steps = self.build.get("steps", [])
        checkout_steps = [s for s in steps if s.get("uses", "").startswith("actions/checkout")]
        self.assertGreater(len(checkout_steps), 0, "build-and-push must have a checkout step")

    def test_build_has_docker_login(self):
        steps = self.build.get("steps", [])
        login_steps = [s for s in steps if "login-action" in s.get("uses", "")]
        self.assertGreater(len(login_steps), 0, "build-and-push must have docker login step")

    def test_build_docker_login_uses_ghcr(self):
        steps = self.build.get("steps", [])
        for s in steps:
            if "login-action" in s.get("uses", ""):
                registry = s.get("with", {}).get("registry", "")
                self.assertEqual(registry, "ghcr.io", "Docker login must use ghcr.io")
                return
        self.fail("Docker login step not found")

    def test_build_has_buildx_setup(self):
        steps = self.build.get("steps", [])
        buildx_steps = [s for s in steps if "setup-buildx-action" in s.get("uses", "")]
        self.assertGreater(len(buildx_steps), 0, "build-and-push must have buildx setup step")

    def test_build_has_web_image_push(self):
        steps = self.build.get("steps", [])
        web_push = [
            s for s in steps
            if "build-push-action" in s.get("uses", "")
            and s.get("with", {}).get("file") == "Dockerfile.web"
        ]
        self.assertGreater(len(web_push), 0, "build-and-push must have web image build step")

    def test_build_web_image_has_correct_tags(self):
        steps = self.build.get("steps", [])
        for s in steps:
            if "build-push-action" in s.get("uses", "") and s.get("with", {}).get("file") == "Dockerfile.web":
                tags = s.get("with", {}).get("tags", "")
                self.assertIn("web:latest", tags, "web image must have latest tag")
                return
        self.fail("Web build-push step not found")

    def test_build_has_worker_image_push(self):
        steps = self.build.get("steps", [])
        worker_push = [
            s for s in steps
            if "build-push-action" in s.get("uses", "")
            and s.get("with", {}).get("file") == "Dockerfile.worker"
        ]
        self.assertGreater(len(worker_push), 0, "build-and-push must have worker image build step")


class JobDependenciesTestCase(unittest.TestCase):
    def setUp(self):
        self.data = load_ci_yml()
        self.jobs = self.data.get("jobs", {})

    def test_test_needs_lint(self):
        needs = self.jobs.get("test", {}).get("needs")
        if isinstance(needs, list):
            self.assertIn("lint", needs)
        else:
            self.assertEqual(needs, "lint", "test job must depend on lint")

    def test_build_needs_test(self):
        needs = self.jobs.get("build-and-push", {}).get("needs")
        if isinstance(needs, list):
            self.assertIn("test", needs)
        else:
            self.assertEqual(needs, "test", "build-and-push job must depend on test")


class CachingTestCase(unittest.TestCase):
    def setUp(self):
        self.data = load_ci_yml()
        self.jobs = self.data.get("jobs", {})
        self.build = self.jobs.get("build-and-push", {})

    def test_web_build_uses_gha_cache_from(self):
        steps = self.build.get("steps", [])
        for s in steps:
            if "build-push-action" in s.get("uses", "") and s.get("with", {}).get("file") == "Dockerfile.web":
                cache_from = s.get("with", {}).get("cache-from", "")
                self.assertIn("gha", cache_from, "web build must use gha cache-from")
                return
        self.fail("Web build-push step not found")

    def test_web_build_uses_gha_cache_to(self):
        steps = self.build.get("steps", [])
        for s in steps:
            if "build-push-action" in s.get("uses", "") and s.get("with", {}).get("file") == "Dockerfile.web":
                cache_to = s.get("with", {}).get("cache-to", "")
                self.assertIn("gha", cache_to, "web build must use gha cache-to")
                return
        self.fail("Web build-push step not found")

    def test_worker_build_uses_gha_cache_from(self):
        steps = self.build.get("steps", [])
        for s in steps:
            if "build-push-action" in s.get("uses", "") and s.get("with", {}).get("file") == "Dockerfile.worker":
                cache_from = s.get("with", {}).get("cache-from", "")
                self.assertIn("gha", cache_from, "worker build must use gha cache-from")
                return
        self.fail("Worker build-push step not found")

    def test_worker_build_uses_gha_cache_to(self):
        steps = self.build.get("steps", [])
        for s in steps:
            if "build-push-action" in s.get("uses", "") and s.get("with", {}).get("file") == "Dockerfile.worker":
                cache_to = s.get("with", {}).get("cache-to", "")
                self.assertIn("gha", cache_to, "worker build must use gha cache-to")
                return
        self.fail("Worker build-push step not found")


if __name__ == "__main__":
    unittest.main()
