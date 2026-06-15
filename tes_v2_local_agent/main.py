import argparse
import sys
import os
from loguru import logger
from tes_v2_local_agent.agents.local_agent import LocalAgent
from tes_v2_local_agent.utils.emergency_stop import EmergencyStop

def main():
    parser = argparse.ArgumentParser(
        description="TES_V2 Local Agent - Intelligent RPA Executor",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Required arguments
    parser.add_argument("--data", required=True, help="Path to source data (JSON or Excel)")
    parser.add_argument("--scenario", required=True, help="Comma-separated list of screen names (e.g. Login,Home,Profile)")

    # Directories
    parser.add_argument("--mappings", default="mappings", help="Directory containing screen mapping JSONs")
    parser.add_argument("--refs", default="reference_screenshots", help="Directory containing reference images")
    parser.add_argument("--popups", default="popups", help="Directory containing popup templates")

    # Execution options
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions without real mouse/keyboard interaction")
    parser.add_argument("--start-from", help="Screen name to start execution from in the scenario")

    args = parser.parse_args()

    # Setup logging
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
    logger.add("agent_execution.log", rotation="10 MB")

    scenario = [s.strip() for s in args.scenario.split(",")]

    # Initialize Emergency Stop
    emergency = EmergencyStop()
    emergency.start()

    try:
        agent = LocalAgent(
            mappings_dir=args.mappings,
            ref_images_dir=args.refs,
            popup_refs_dir=args.popups if os.path.exists(args.popups) else None,
            dry_run=args.dry_run
        )

        agent.run_scenario(
            data_file=args.data,
            scenario=scenario,
            start_from_screen=args.start_from
        )

    except KeyboardInterrupt:
        logger.warning("Agent stopped by user.")
    except Exception as e:
        logger.exception(f"Unexpected error during execution: {e}")
    finally:
        emergency.stop()
        logger.info("Agent session finished.")

if __name__ == "__main__":
    main()
