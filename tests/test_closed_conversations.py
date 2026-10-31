"""Closing a conversation ends what its token can do. The answer stays 409
conversation_closed rather than 401, so a page still open tells the customer the
truth instead of asking them to sign in."""

from tests.test_api import LAYLA, V1, client, say, signed_in, start, state_of  # noqa: F401


def close(test_client, cid):
    csrf = signed_in(test_client)
    assert test_client.post(f"{V1}/desk/conversations/{cid}/close", headers=csrf).status_code == 200


def test_closing_a_conversation_ends_what_its_token_can_do(client):  # noqa: F811
    cid, auth = start(client)
    close(client, cid)
    attempts = [
        client.post(f"{V1}/conversations/{cid}/verify/start", headers=auth, json={"phone": LAYLA}),
        client.post(f"{V1}/conversations/{cid}/verify/confirm", headers=auth, json={"code": "123456"}),
        client.post(f"{V1}/conversations/{cid}/handoff", headers=auth, json={}),
        say(client, cid, auth, "one more thing", "c2"),
    ]
    assert [response.status_code for response in attempts] == [409] * 4
    assert {response.json()["error"]["code"] for response in attempts} == {"conversation_closed"}


def test_a_handoff_cannot_put_a_closed_conversation_back_in_the_queue(client):  # noqa: F811
    cid, auth = start(client)
    close(client, cid)
    client.post(f"{V1}/conversations/{cid}/handoff", headers=auth, json={})
    assert state_of(client, cid) == "closed"


def test_a_closed_conversation_still_turns_away_a_wrong_token(client):  # noqa: F811
    cid, _ = start(client)
    close(client, cid)
    response = client.post(f"{V1}/conversations/{cid}/handoff", headers={"Authorization": "Bearer nope"}, json={})
    assert response.status_code == 401
