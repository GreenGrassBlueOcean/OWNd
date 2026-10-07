"""WHO 18 dimension 1200 reply: *#18*W*1200#type*time## confirms (time > 0)
or ends (time = 0) the automatic power updates. libqtdevices TS10_1_0_23
energy_device.cpp:111 (_DIM_STATE_UPDATE_INTERVAL = 1200), :289-322
(handleAutomaticUpdate re-arms on time = 0), :719-726, :50-56 (energy types).
Firmware replay on bt_supervisione (MyHomeServer1, F454, F459, F461):
*#18*51*#1200#1*255## ACK bus D1 A1 02 32 00 02 1D FF, #1200#1*0 ... 1D 00,
#1200#2*255 ... 82 FF; the bare *#18*51*1200## is NACK with no bus frame."""

from OWNd.message import MESSAGE_TYPE_AUTO_UPDATE_INTERVAL, OWNEnergyEvent, OWNEvent


def test_auto_update_confirmation_is_parsed():
    msg = OWNEvent.parse("*#18*51*1200#1*255##")
    assert isinstance(msg, OWNEnergyEvent)
    assert msg.message_type == MESSAGE_TYPE_AUTO_UPDATE_INTERVAL
    assert msg.update_interval == 255
    assert msg.energy_type == 1
    assert "255 s" in msg.human_readable_log


def test_auto_update_stop_is_parsed():
    msg = OWNEvent.parse("*#18*51*1200#1*0##")
    assert msg.message_type == MESSAGE_TYPE_AUTO_UPDATE_INTERVAL
    assert msg.update_interval == 0


def test_other_dimensions_are_untouched():
    msg = OWNEvent.parse("*#18*51*113*1234##")
    assert msg.update_interval is None
    assert msg.energy_type is None
    assert msg.message_type != MESSAGE_TYPE_AUTO_UPDATE_INTERVAL
