"""Tests for the simulation engine (ADLC Test Phase)."""

import unittest

from sentinel.test.simulations import (
    DEFAULT_SCENARIOS,
    SimulationResult,
    SimulationStep,
    create_bad_to_good_scenario,
    create_no_regression_scenario,
    create_severity_improvement_scenario,
    run_simulations,
)


class TestSimulationConcepts(unittest.TestCase):
    def test_step_defaults(self):
        step = SimulationStep(content="x = 1")
        self.assertEqual(step.file_path, "simulation.py")
        self.assertIsNone(step.expected_finding_range)
        self.assertIsNone(step.expected_rule_ids)

    def test_scenario_creation(self):
        scenario = create_bad_to_good_scenario()
        self.assertEqual(len(scenario.steps), 2)
        self.assertEqual(scenario.name, "Bad to Good (findings decrease)")

    def test_no_regression_scenario_creation(self):
        scenario = create_no_regression_scenario()
        self.assertEqual(len(scenario.steps), 2)
        self.assertIn("No regression", scenario.name)

    def test_severity_improvement_scenario_creation(self):
        scenario = create_severity_improvement_scenario()
        self.assertEqual(len(scenario.steps), 2)
        self.assertIn("Severity improves", scenario.name)

    def test_default_scenarios_defined(self):
        self.assertEqual(len(DEFAULT_SCENARIOS), 3)

    def test_result_properties(self):
        result = SimulationResult(name="test", steps=[])
        self.assertTrue(result.passed)
        self.assertEqual(result.total_steps, 0)
        self.assertEqual(result.passed_steps, 0)

    def test_result_with_failures(self):
        from sentinel.test.simulations import SimulationStepResult

        step = SimulationStepResult(
            step_index=0,
            findings_count=5,
            findings=[],
            duration_ms=10.0,
            passed=False,
            rule_ids_found=set(),
            rule_ids_missing=["SEC001"],
        )
        result = SimulationResult(name="failing", steps=[step])
        self.assertFalse(result.passed)
        self.assertEqual(result.passed_steps, 0)
        self.assertEqual(result.total_steps, 1)

    def test_run_simulations_smoke(self):
        results = run_simulations(verbose=False)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIsInstance(r, SimulationResult)


if __name__ == "__main__":
    unittest.main()
