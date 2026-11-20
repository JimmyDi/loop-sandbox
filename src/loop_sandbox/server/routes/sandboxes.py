from fastapi import APIRouter

from loop_sandbox.server.lifecycle import close_sandbox, list_sandboxes, open_sandbox

router = APIRouter()
router.add_api_route("/sandboxes", open_sandbox, methods=["POST"])
router.add_api_route("/sandboxes", list_sandboxes, methods=["GET"])
router.add_api_route("/sandboxes/{sid}", close_sandbox, methods=["DELETE"])
