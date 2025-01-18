import os
from typing import List

from pushbullet import Pushbullet

from src import logger
from src.constants import MAX_NUM_ITEMS_TO_NOTIFY, TARGET_TO_EMOJI


async def send_notifications(
    flight_data: List[dict],
    target: str,
    alt_diff_threshold: float,
    az_diff_threshold: float,
) -> None:
    """Send a notification with the possible transits. Send a maximum of 5 transits."""
    API_TOKEN = os.getenv("PUSH_BULLET_API_KEY")

    if not API_TOKEN:
        logger.warning("No API token to send notifications, skipping...")

    possible_transits_data = list()

    for flight in flight_data:
        if (
            flight["is_possible_transit"] == 1
            and flight["alt_diff"] <= alt_diff_threshold
            and flight["az_diff"] <= az_diff_threshold
        ):
            diff_sum = flight["alt_diff"] + flight["az_diff"]
            possible_transits_data.append(
                f"{flight['id']} in {flight['time']} m."
                f" {flight['origin']}->{flight['destination']}"
                f" △{diff_sum}"
            )

        if len(possible_transits_data) >= MAX_NUM_ITEMS_TO_NOTIFY:
            break

    if len(possible_transits_data) == 0:
        logger.warning("No transits to notify, skipping...")
        return

    pb = Pushbullet(API_TOKEN)

    body_message = "\n".join(possible_transits_data)
    emoji = TARGET_TO_EMOJI.get(target, "")

    transit_txt = "transit" if len(possible_transits_data) == 1 else "transits"

    response = pb.push_note(
        title=f"{len(possible_transits_data)} possible {transit_txt} {emoji}",
        body=body_message,
    )

    logger.info("notification sent!")
