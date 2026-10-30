"""ACCEPT-01: the end-to-end acceptance matrix.

Every workflow the plan names needs four kinds of coverage: success, refusal,
recovery, and no mutation on failure. Each cell lists the tests that provide
it. This file is checked: a cell must not be empty, and every test named must
exist and run in the default suite (no `slow` mark).

Each cited test was read when the matrix was written (2026-10-30) to confirm it
asserts what its cell claims, not only that its name suggests it. Cells that
had no such test were filled by `test_accept_*.py`.
"""
from __future__ import annotations

import importlib

import pytest

KINDS = ("success", "refusal", "recovery", "no_mutation_on_failure")

MATRIX: dict[str, dict[str, list[str]]] = {
    "research intake": {
        "success": ["test_intake::test_repository_capture_to_catalogued",
                    "test_intake::test_paper_capture_to_catalogued"],
        "refusal": ["test_research_loop::test_a_topic_not_asked_is_refused",
                    "test_research_loop::test_coverage_verdicts_are_earned_and_context_is_not_an_answer",
                    "test_intake::test_screen_reject_is_recorded_on_the_candidate_not_staged"],
        "recovery": ["test_intake::test_queue_then_run",
                     "test_research_loop::test_a_spent_budget_is_not_a_dead_end"],
        "no_mutation_on_failure": [
            "test_accept_failures::test_a_failed_intake_catalogues_stages_and_records_nothing"],
    },
    "evidence, staging and promotion": {
        "success": ["test_staging::test_person_accepts_and_it_is_catalogued",
                    "test_evidence::test_content_addressed_and_idempotent"],
        "refusal": ["test_staging::test_sensitive_is_never_accepted_by_an_agent",
                    "test_staging_safety::test_an_active_document_lease_blocks_the_merge",
                    "test_evidence::test_framing_is_refused_at_any_depth"],
        "recovery": [
            "test_core_source_promotion::test_interrupted_acceptance_can_be_explicitly_finished_after_restart",
            "test_staging_safety::test_staging_dependency_operation_log_remains_readable_after_restart"],
        "no_mutation_on_failure": [
            "test_core_source_promotion::test_preflight_failure_never_copies_an_attachment",
            "test_core_source_promotion::test_dry_run_predicts_copies_without_changing_files_or_staged_json",
            "test_staging_safety::test_a_note_edited_since_review_is_not_merged"],
    },
    "V1 import": {
        "success": ["test_v1_export::test_v1_import_binds_one_root_and_accepts_an_explicit_subset",
                    "test_v1_export::test_accepted_notes_keep_everything_v1_had"],
        "refusal": ["test_v2_remediation::test_agent_context_cannot_start_exec_select_ranking_or_stage_v1",
                    "test_accept_failures::test_a_v1_import_from_a_second_root_stages_nothing"],
        "recovery": ["test_v1_export::test_only_what_v1_ingested_is_staged_and_v1_is_untouched",
                     "test_v1_export::test_a_note_already_held_is_not_staged_again"],
        "no_mutation_on_failure": ["test_accept_failures::test_a_refused_v1_import_stages_nothing"],
    },
    "profiles, bundles, macros and checkpoints": {
        "success": ["test_agent_runtime_profiles::test_delegated_helper_uses_its_versioned_read_only_profile",
                    "test_agent_runtime_profiles::test_profile_store_versions_each_vault_scoped_edit"],
        "refusal": ["test_agent_runtime_profiles::test_compact_bundle_is_also_an_execution_boundary",
                    "test_macro_permissions::test_macro_nested_in_writer_refuses_before_asking_permission",
                    "test_v2_remediation::test_expired_checkpoint_cannot_authorize_a_later_operation"],
        "recovery": ["test_macro_permissions::test_macro_permissions_wait_outside_writer_and_keep_completed_work",
                     "test_v2_remediation::test_expired_checkpoint_cannot_authorize_a_later_operation"],
        "no_mutation_on_failure": [
            "test_macro_permissions::test_macro_approval_never_overrides_a_denied_step_or_plan_mode",
            "test_macro_permissions::test_macro_checkpoint_is_invalid_after_plan_changes_without_version_bump",
            "test_agent_runtime_profiles::test_profile_token_and_unpriced_cost_budgets_fail_before_a_provider_call"],
    },
    "Browser, Obsidian and Cowork lifecycle": {
        "success": ["test_shutdown::test_an_idle_stop_records_every_phase_and_releases_the_lease",
                    "test_host_lifecycle::test_host_managed_core_starts_and_stops_cleanly",
                    "test_packaged_adapter_smoke::test_browser_and_cowork_overlap_on_one_core_then_cleanup"],
        "refusal": ["test_shutdown::test_a_person_call_after_the_stop_is_refused",
                    "test_shutdown::test_direct_configuration_offering_and_checkpoint_mutations_refuse_after_admission_closes",
                    "test_obsidian_adapter_contract::test_obsidian_discovery_validates_exact_core_identity_before_using_token"],
        "recovery": ["test_shutdown::test_a_thread_cut_off_by_the_stop_reopens_parked_and_resumable",
                     "test_host_lifecycle::test_host_start_ignores_its_own_row_once_the_pid_is_recycled"],
        "no_mutation_on_failure": [
            "test_accept_failures::test_mutations_refused_after_shutdown_admission_closes_change_nothing"],
    },
    "service slots": {
        "success": ["test_route_picker_snapshot::test_the_picker_and_service_slots_match_the_golden_snapshot",
                    "test_role_route_bindings::test_service_slots_mirror_validated_choices_without_chat_qualification"],
        "refusal": ["test_service_routes::test_changed_disabled_missing_and_stopped_routes_never_make_a_call",
                    "test_service_routes::test_unavailable_service_host_stays_visible_but_cannot_execute"],
        "recovery": ["test_service_routes::test_service_assignment_survives_projection_changes_and_restart",
                     "test_service_routes::test_service_result_after_stop_is_discarded_and_visible_during_drain"],
        "no_mutation_on_failure": [
            "test_accept_failures::test_a_refused_service_choice_changes_no_slot_and_no_binding"],
    },
    "Workbench execution labelling": {
        "success": ["test_accept_workbench::test_success_inspect_only_is_labelled_and_runs_nothing",
                    "test_accept_workbench::test_success_host_execution_is_labelled_non_isolated_with_its_warning",
                    "test_accept_workbench::test_success_docker_execution_is_labelled_isolated"],
        "refusal": ["test_accept_workbench::test_refusal_an_agent_cannot_start_execution",
                    "test_v2_remediation::test_execution_and_forced_close_are_explicit_ui_checkpoints"],
        "recovery": [
            "test_accept_workbench::test_recovery_a_failed_run_pauses_keeps_its_label_and_can_run_again"],
        "no_mutation_on_failure": [
            "test_accept_workbench::test_refusal_and_no_mutation_a_refused_start_records_nothing"],
    },
    "manual ranking": {
        "success": [
            "test_accept_ranking::test_success_a_person_selects_a_candidate_and_search_uses_its_weights"],
        "refusal": ["test_accept_ranking::test_refusal_an_agent_cannot_select_or_restore_a_policy",
                    "test_accept_ranking::test_refusal_too_little_feedback_proposes_nothing"],
        "recovery": ["test_accept_ranking::test_recovery_restore_returns_to_the_previous_policy",
                     "test_accept_ranking::test_recovery_a_damaged_experiment_file_never_breaks_search"],
        "no_mutation_on_failure": [
            "test_accept_ranking::test_no_mutation_selecting_an_unknown_candidate_changes_nothing"],
    },
}

CELLS = [(w, k) for w in MATRIX for k in KINDS]


@pytest.mark.parametrize("workflow,kind", CELLS)
def test_every_cell_is_covered_by_tests_that_run_by_default(workflow, kind):
    cited = MATRIX[workflow].get(kind) or []
    assert cited, f"{workflow}: no {kind} coverage"
    for ident in cited:
        module_name, test_name = ident.split("::")
        module = importlib.import_module(module_name)
        test = getattr(module, test_name, None)
        assert callable(test), f"{ident} does not exist"
        marks = {m.name for m in getattr(test, "pytestmark", [])}
        assert "slow" not in marks and "skip" not in marks, f"{ident} does not run by default"


def test_the_matrix_names_every_workflow_in_the_plan():
    assert list(MATRIX) == [
        "research intake", "evidence, staging and promotion", "V1 import",
        "profiles, bundles, macros and checkpoints", "Browser, Obsidian and Cowork lifecycle",
        "service slots", "Workbench execution labelling", "manual ranking"]
