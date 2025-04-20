import pytest
import os
from app import send_telegram

def test_current_status_cycle(client):  #tests for the /current_status and /anomaly endpoints to ensure correct cycling through data points
    #power = 1.0 so no anomaly expected
    rv1 = client.get('/current_status?resolution=minute')
    assert rv1.status_code == 200
    j1 = rv1.get_json()
    assert j1['latestPower'] == 1.0
    assert j1['anomalyFound'] is False
    #verify date string ends with "/2025"
    assert j1['date'].endswith('/2025')

    #power = 1.2 so still no anomaly
    rv2 = client.get('/current_status?resolution=minute')
    j2 = rv2.get_json()
    assert j2['latestPower'] == 1.2
    assert j2['anomalyFound'] is False

    #power = 5.0 so anomaly expected
    rv3 = client.get('/current_status?resolution=minute')
    j3 = rv3.get_json()
    assert j3['latestPower'] == 5.0
    assert j3['anomalyFound'] is True

    #power = 1.1 so back to no anomaly
    rv4 = client.get('/current_status?resolution=minute')
    j4 = rv4.get_json()
    assert j4['latestPower'] == 1.1
    assert j4['anomalyFound'] is False

def test_anomaly_alias(client):   #ensure that /anomaly is an alias for /current_status and returns identical JSON
    r1 = client.get('/current_status?resolution=minute').get_json()
    r2 = client.get('/anomaly?resolution=minute').get_json()
    assert r1 == r2

def test_insights_endpoint(client):  #test /insights returns correct deltaKw and sevenPctChange calculations
    import app as m
    #advance index so idx >= 2 to have at least two data points to compare
    m.current_index = 3
    rv = client.get('/insights')
    assert rv.status_code == 200
    js = rv.get_json()
    #deltaKw = last (5.0) - prev (1.2) = 3.8
    assert pytest.approx(js['deltaKw'], rel=1e-3) == 3.8
    #with only four data points, sevenPctChange should be default 0.0
    assert js['sevenPctChange'] == 0.0

#parameterised tests for /tips to cover different percentage and deltaKw scenarios
@pytest.mark.parametrize("pct,dk,contains", [
    (-5, 0.1, "cutting your average"),
    (10, 0.6, "spike this period"),
])
def test_tips_endpoint(client, pct, dk, contains):
    rv = client.get(f'/tips?sevenPctChange={pct}&deltaKw={dk}')
    assert rv.status_code == 200
    tips = rv.get_json()['tips']
    #expect at least two tips returned
    assert len(tips) >= 2
    #one of the tips should contain the specified substring
    assert any(contains in t for t in tips)
 
def test_index_route_serves_html(client):  #test that the root index route serves HTML (index.html)
    #GET / should return index.html with HTML content
    rv = client.get('/')
    assert rv.status_code == 200
    #check for opening HTML tag or doctype
    assert b"<html" in rv.data.lower() or b"<!doctype html" in rv.data.lower()

def test_send_telegram_no_token(monkeypatch):  #tests for send_telegram, behavior when no token/ID and when both are provided
    #If no TELEGRAM_BOT_TOKEN/CHAT_ID, send_telegram should not call requests.post
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID",   raising=False)

    calls = []
    #Monkeypatch requests.post to record calls
    monkeypatch.setattr(send_telegram.__globals__['requests'], "post",
                        lambda *args, **kwargs: calls.append((args,kwargs)))
    send_telegram("hello")
    #expect no HTTP requests made
    assert calls == []

def test_send_telegram_success(monkeypatch):     #with valid token & chat_id, send_telegram calls requests.post once with correct payload
    #set environment variables for bot and chat
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID",  "fake-chat")

    calls = []
    #fake requests.post to capture its arguments
    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        class Resp: pass
        return Resp()
    monkeypatch.setattr(send_telegram.__globals__['requests'], "post", fake_post)

    send_telegram("THIS_IS_A_TEST")
    #exactly one HTTP call should have been made
    assert len(calls) == 1
    url, payload, to = calls[0]
    #URL should include the bot token
    assert "fake-token" in url
    #JSON payload keys and values
    assert payload["chat_id"] == "fake-chat"
    assert payload["text"] == "THIS_IS_A_TEST"
    assert payload["parse_mode"] == "Markdown"
    #confirm timeout argument was passed as expected
    assert to == 5
