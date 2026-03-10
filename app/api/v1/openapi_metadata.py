from fastapi import FastAPI
from fastapi.routing import APIRoute


SUMMARY_OVERRIDES = {
    "me": "Get Current User",
    "login": "Log In",
    "refresh": "Refresh Tokens",
    "get_recommendations": "Get Recommended Competencies",
    "parse_all_jobs_for_profession": "Parse All Jobs for Profession",
    "recalculate_profession_competencies": "Recalculate Profession Competencies",
    "parse_job_competencies": "Parse Job Competencies",
    "upload_candidate_cv": "Upload Candidate CV",
    "delete_candidate_cv": "Delete Candidate CV",
    "get_candidate_cv_url": "Get Candidate CV URL",
    "parse_candidate_cv": "Parse Candidate CV",
    "calculate_model": "Calculate OPA Result",
    "calculate_vikor": "Calculate VIKOR Result",
    "get_results": "Get Selection Results",
    "expert_accept_invite": "Accept Competency Model Invite",
    "expert_accept_selection_invite": "Accept Selection Invite",
    "expert_submit_evaluation": "Submit Competency Model Evaluation",
    "expert_submit_scores": "Submit Candidate Scores",
    "expert_evaluation_status": "Get Evaluation Status",
    "expert_scoring_status": "Get Scoring Status",
}

DESCRIPTION_OVERRIDES = {
    "register": "Create a new user account and return the created user profile.",
    "login": "Authenticate a user and return a new access token pair.",
    "refresh": "Issue a new access token pair using a valid refresh token.",
    "me": "Return the currently authenticated user.",
    "create_profession_group": "Create a profession group. This endpoint is available to admin users only.",
    "update_profession_group": "Update a profession group. This endpoint is available to admin users only.",
    "delete_profession_group": "Delete a profession group. This endpoint is available to admin users only.",
    "create_profession": "Create a profession. This endpoint is available to admin users only.",
    "update_profession": "Update a profession. This endpoint is available to admin users only.",
    "delete_profession": "Delete a profession. This endpoint is available to admin users only.",
    "create_profession_collection": "Create a profession collection. This endpoint is available to admin users only.",
    "update_profession_collection": "Update a profession collection. This endpoint is available to admin users only.",
    "delete_profession_collection": "Delete a profession collection. This endpoint is available to admin users only.",
    "add_profession_collection_member": "Add a profession to a collection. This endpoint is available to admin users only.",
    "delete_profession_collection_member": "Remove a profession from a collection. This endpoint is available to admin users only.",
    "create_profession_label": (
        "Create a label for a profession. This endpoint is available to admin users only. "
        "Valid label_type values are preferred, alternative, and hidden. "
        "preferred is the primary display label, alternative is a synonym, and hidden is a search-only alias."
    ),
    "update_profession_label": (
        "Update a profession label. This endpoint is available to admin users only. "
        "Valid label_type values are preferred, alternative, and hidden. "
        "preferred is the primary display label, alternative is a synonym, and hidden is a search-only alias."
    ),
    "delete_profession_label": "Delete a profession label. This endpoint is available to admin users only.",
    "create_competency_group": "Create a competency group. This endpoint is available to admin users only.",
    "update_competency_group": "Update a competency group. This endpoint is available to admin users only.",
    "delete_competency_group": "Delete a competency group. This endpoint is available to admin users only.",
    "create_competency_label": (
        "Create a label for a competency. This endpoint is available to admin users only. "
        "Valid label_type values are preferred, alternative, and hidden. "
        "preferred is the primary display label, alternative is a synonym, and hidden is a search-only alias."
    ),
    "update_competency_label": (
        "Update a competency label. This endpoint is available to admin users only. "
        "Valid label_type values are preferred, alternative, and hidden. "
        "preferred is the primary display label, alternative is a synonym, and hidden is a search-only alias."
    ),
    "delete_competency_label": "Delete a competency label. This endpoint is available to admin users only.",
    "create_competency": (
        "Create a competency. This endpoint is available to admin users only. "
        "Valid competency_type values are skill/competence and knowledge."
    ),
    "update_competency": (
        "Update a competency. This endpoint is available to admin users only. "
        "Valid competency_type values are skill/competence and knowledge."
    ),
    "delete_competency": "Delete a competency. This endpoint is available to admin users only.",
    "add_competency_to_group": "Add a competency to a competency group. This endpoint is available to admin users only.",
    "remove_competency_from_group": "Remove a competency from a competency group. This endpoint is available to admin users only.",
    "create_competency_relation": (
        "Create a semantic relation between two competencies. This endpoint is available to admin users only. "
        "Valid relation_type values are essential, optional, and related."
    ),
    "delete_competency_relation": (
        "Delete a semantic relation between two competencies. "
        "The relation_type path segment must be one of essential, optional, or related. "
        "This endpoint is available to admin users only."
    ),
    "create_competency_collection": "Create a competency collection. This endpoint is available to admin users only.",
    "update_competency_collection": "Update a competency collection. This endpoint is available to admin users only.",
    "delete_competency_collection": "Delete a competency collection. This endpoint is available to admin users only.",
    "add_competency_collection_member": "Add a competency to a collection. This endpoint is available to admin users only.",
    "delete_competency_collection_member": "Remove a competency from a collection. This endpoint is available to admin users only.",
    "add_profession_competency": (
        "Create a manual profession-competency link. This endpoint is available to admin users only. "
        "Only link_type=manual is accepted through this endpoint. "
        "Other link types are generated by ESCO import and vacancy parsing workflows. "
        "Use weight to store the manual importance assigned by the user."
    ),
    "update_profession_competency": (
        "Update a profession-competency link. This endpoint is available to admin users only. "
        "Only manual links can be updated through this endpoint. "
        "The link_type path segment can contain esco_essential, esco_optional, job_derived, or manual, "
        "but only manual records are editable."
    ),
    "delete_profession_competency": (
        "Delete a profession-competency link. This endpoint is available to admin users only. "
        "The link_type path segment can contain esco_essential, esco_optional, job_derived, or manual."
    ),
    "create_job": "Create a job record. This endpoint is available to admin users only.",
    "update_job": "Update a job record. This endpoint is available to admin users only.",
    "delete_job": "Delete a job record. This endpoint is available to admin users only.",
    "add_job_competency": "Add a competency link to a job manually. This endpoint is available to admin users only.",
    "delete_job_competency": "Delete a manual or parsed competency link from a job. This endpoint is available to admin users only.",
    "submit_model": (
        "Move the competency model from DRAFT to EXPERT_EVALUATION and persist submission filters. "
        "At least one of min_competency_weight or max_competency_rank must be provided. "
        "Available only when the model status is DRAFT."
    ),
    "cancel_model": "Cancel the selected competency model. This operation is not available once the model is completed or already cancelled.",
    "calculate_model": "Run the OPA calculation for the competency model and return the final ranking result. Available only when the model status is EXPERT_EVALUATION.",
    "update_model": "Update the competency model metadata. Available only when the model status is DRAFT.",
    "delete_model": "Delete the competency model. Available only when the model status is DRAFT.",
    "add_expert": (
        "Add a registered user as an expert. "
        "For competency models this is available only when the model status is DRAFT. "
        "For candidate selections this is available only when the selection status is DRAFT."
    ),
    "update_expert": "Update expert settings. Available only when the parent model is in DRAFT status.",
    "remove_expert": (
        "Remove an expert. "
        "For competency models this is available only when the model status is DRAFT. "
        "For candidate selections this is available only when the selection status is DRAFT."
    ),
    "create_expert_invite": (
        "Create an email invite for an expert. "
        "For competency models this is available only when the model status is DRAFT. "
        "For candidate selections this is available only when the selection status is DRAFT."
    ),
    "update_expert_invite": (
        "Update an expert invite. "
        "For competency models this is available only when the model status is DRAFT and before the invite is accepted. "
        "For candidate selections this is available only when the selection status is DRAFT and before the invite is accepted."
    ),
    "delete_expert_invite": (
        "Delete an expert invite. "
        "For competency models this is available only when the model status is DRAFT. "
        "For candidate selections this is available only when the selection status is DRAFT."
    ),
    "add_criterion": "Add an evaluation criterion to the competency model. Available only when the model status is DRAFT.",
    "update_criterion": "Update an evaluation criterion. Available only when the model status is DRAFT.",
    "remove_criterion": "Remove an evaluation criterion. Available only when the model status is DRAFT.",
    "add_alternative": "Add a competency alternative to the competency model. Available only when the model status is DRAFT.",
    "remove_alternative": "Remove a competency alternative from the competency model. Available only when the model status is DRAFT.",
    "get_recommendations": (
        "Return suggested competencies for the selected profession, including whether they were already added to the model. "
        "Recommendations are based on profession-competency links, prioritizing ESCO essential links, then manual links, "
        "then ESCO optional links, and finally job-derived links."
    ),
    "expert_list_models": "Return competency models assigned to the current expert.",
    "expert_list_invites": "Return pending competency model invites for the current expert.",
    "expert_accept_invite": "Accept a competency model invite using the invite token.",
    "expert_evaluation_status": "Return the current expert's completion status for a competency model evaluation. Available only for experts assigned to that model.",
    "expert_submit_evaluation": "Submit expert rankings for criteria and alternatives in a competency model. Available only while the model status is EXPERT_EVALUATION and before the deadline, if one is set.",
    "create_selection": "Create a candidate selection from an existing completed competency model.",
    "update_selection": "Update selection metadata. Available only when the selection status is DRAFT.",
    "delete_selection": "Delete the selection. Available only when the selection status is DRAFT.",
    "submit_selection": "Move the selection from draft to expert scoring. Available only when the selection status is DRAFT.",
    "cancel_selection": "Cancel the selected candidate selection. This operation is not available once the selection is completed or already cancelled.",
    "calculate_vikor": "Run the VIKOR calculation for a selection and return the final ranking. Available only after all required expert scores are submitted.",
    "get_results": "Return the stored VIKOR result for the selected candidate selection.",
    "list_candidates": "Return candidates created by the current authenticated user.",
    "create_candidate": "Create a candidate record owned by the current authenticated user.",
    "get_candidate": "Return a candidate with the currently stored extracted competencies. Available only to the candidate owner.",
    "upload_candidate_cv": "Upload a CV file for the selected candidate and store it in Supabase Storage. Available only to the candidate owner.",
    "delete_candidate_cv": "Delete the stored CV file for the selected candidate and clear its metadata. Available only to the candidate owner.",
    "get_candidate_cv_url": "Generate a signed URL for downloading the candidate's CV file. Available only to the candidate owner.",
    "parse_candidate_cv": "Parse the stored candidate CV file and update the candidate's extracted competencies. Available only to the candidate owner and requires an uploaded CV file.",
    "add_candidate_to_selection": "Add an existing candidate to a selection. Available only when the selection status is DRAFT.",
    "remove_candidate_from_selection": "Remove a candidate from a selection. Available only when the selection status is DRAFT.",
    "parse_job_competencies": (
        "Parse the selected job description, extract matched competencies, and replace the current job-competency links "
        "for that vacancy with the new parsing result. This endpoint is available to admin users only."
    ),
    "parse_all_jobs_for_profession": (
        "Parse all jobs linked to the selected profession. Each job description is processed independently and its "
        "job-competency links are refreshed from the parsing result. "
        "This endpoint is available to admin users only. "
        "Use it after importing or updating vacancies for a profession."
    ),
    "recalculate_profession_competencies": (
        "Rebuild job-derived profession competency links for the selected profession using the parsed job data. "
        "Derived weights are stored as job frequencies within that profession. "
        "This endpoint is available to admin users only and should usually be called after parsing all jobs for the profession."
    ),
    "expert_list_selections": "Return candidate selections assigned to the current expert.",
    "expert_list_selection_invites": "Return pending candidate selection invites for the current expert.",
    "expert_accept_selection_invite": "Accept a candidate selection invite using the invite token.",
    "expert_scoring_status": "Return the current expert's completion status for candidate scoring. Available only for experts assigned to that selection.",
    "expert_submit_scores": (
        "Submit candidate scores for the competencies used in the selected evaluation. "
        "Available only while the selection status is EXPERT_SCORING. "
        "Scores may be provided only for candidates included in the selection and for competencies taken from the linked competency model. "
        "Each score must be in the 1..5 range."
    ),
}

VERB_TEMPLATES = {
    "list": "Return a list of {object}.",
    "get": "Return {object}.",
    "create": "Create {object}.",
    "update": "Update {object}.",
    "delete": "Delete {object}.",
    "remove": "Remove {object}.",
    "add": "Add {object}.",
    "submit": "Submit {object}.",
    "cancel": "Cancel {object}.",
    "calculate": "Calculate {object}.",
    "parse": "Parse {object}.",
    "upload": "Upload {object}.",
    "accept": "Accept {object}.",
    "refresh": "Refresh {object}.",
}

VERB_LABELS = {
    "list": "List",
    "get": "Get",
    "create": "Create",
    "update": "Update",
    "delete": "Delete",
    "remove": "Remove",
    "add": "Add",
    "submit": "Submit",
    "cancel": "Cancel",
    "calculate": "Calculate",
    "parse": "Parse",
    "upload": "Upload",
    "accept": "Accept",
    "refresh": "Refresh",
}


def _humanize_name(name: str) -> tuple[str, str]:
    parts = name.split("_")
    verb = parts[0]
    obj = " ".join(parts[1:]) if len(parts) > 1 else name
    summary = f"{VERB_LABELS.get(verb, parts[0].title())} {' '.join(word.title() for word in parts[1:])}".strip()
    description = VERB_TEMPLATES.get(verb, "Perform the {object} operation.").format(object=obj.replace("_", " "))
    return summary, description[:1].upper() + description[1:]


def apply_openapi_metadata(app: FastAPI) -> None:
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue

        if route.name in SUMMARY_OVERRIDES:
            route.summary = SUMMARY_OVERRIDES[route.name]
        else:
            route.summary, _ = _humanize_name(route.name)

        if route.name in DESCRIPTION_OVERRIDES:
            route.description = DESCRIPTION_OVERRIDES[route.name]
        else:
            _, generated_description = _humanize_name(route.name)
            route.description = generated_description
