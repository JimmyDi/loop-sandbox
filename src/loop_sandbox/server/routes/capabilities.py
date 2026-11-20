from fastapi import APIRouter

from loop_sandbox.server.client import browser, commands, download, read, write

router = APIRouter()
router.add_api_route("/sandboxes/{sid}/commands", commands, methods=["POST"])
router.add_api_route("/sandboxes/{sid}/files", write, methods=["POST"])
router.add_api_route("/sandboxes/{sid}/files", read, methods=["GET"])
router.add_api_route("/sandboxes/{sid}/download", download, methods=["GET"])
router.add_api_route("/sandboxes/{sid}/browser", browser, methods=["POST"])
