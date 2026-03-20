import React, { useState, useEffect } from "react";
import { View, Text, TouchableOpacity, Linking } from "react-native";
import { colors } from "../../theme/colors";
import { spotifyStatus, spotifyDevices, spotifyConnectUrl, spotifyDisconnect } from "../../lib/api";
import { Label, CardRow, st, TabProps } from "./shared";

export default function TabSpotify(_props: TabProps) {
  const [spotifyConnected, setSpotifyConnected] = useState(false);
  const [spotifyUser, setSpotifyUser] = useState("");
  const [spotifyDeviceList, setSpotifyDeviceList] = useState<any[]>([]);
  const [spotifyLoading, setSpotifyLoading] = useState(false);

  useEffect(() => {
    setSpotifyLoading(true);
    spotifyStatus().then((r) => {
      setSpotifyConnected(!!r.connected);
      setSpotifyUser(r.display_name || r.user || "");
    }).catch(() => {}).finally(() => setSpotifyLoading(false));
    spotifyDevices().then((r) => setSpotifyDeviceList(r.devices || [])).catch(() => {});
  }, []);

  return (
    <>
      <Text style={st.desc}>Connect your Spotify account to control playback.</Text>

      {/* Connection status */}
      <View style={st.card}>
        <CardRow label="Status" value={spotifyConnected ? "Connected" : "Not connected"}
          valueColor={spotifyConnected ? colors.success : colors.labelTertiary} />
        {spotifyUser ? <CardRow label="Account" value={spotifyUser} /> : null}
      </View>

      {/* Connect / Disconnect */}
      {spotifyConnected ? (
        <TouchableOpacity style={[st.accentBtn, { backgroundColor: colors.dangerSubtle }]}
          onPress={async () => {
            await spotifyDisconnect().catch(() => {});
            setSpotifyConnected(false);
            setSpotifyUser("");
            setSpotifyDeviceList([]);
          }}
          activeOpacity={0.7}>
          <Text style={[st.accentBtnText, { color: colors.danger }]}>Disconnect</Text>
        </TouchableOpacity>
      ) : (
        <TouchableOpacity style={st.accentBtn}
          onPress={async () => {
            const url = await spotifyConnectUrl();
            Linking.openURL(url).catch(() => {});
          }}
          disabled={spotifyLoading}
          activeOpacity={0.7}>
          <Text style={st.accentBtnText}>{spotifyLoading ? "Loading..." : "Connect Spotify"}</Text>
        </TouchableOpacity>
      )}

      {/* Devices */}
      {spotifyConnected && spotifyDeviceList.length > 0 && (
        <>
          <Label text="Devices" />
          {spotifyDeviceList.map((d: any, i: number) => (
            <View key={d.id || i} style={st.toggleRow}>
              <View style={{ flex: 1 }}>
                <Text style={st.toggleName}>{d.name}</Text>
                <Text style={st.toggleDesc}>{d.type}{d.is_active ? " • Active" : ""}</Text>
              </View>
              {d.is_active && <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: colors.success }} />}
            </View>
          ))}
          <TouchableOpacity style={[st.accentBtn, { backgroundColor: colors.white08, marginTop: 8 }]}
            onPress={() => { spotifyDevices().then((r) => setSpotifyDeviceList(r.devices || [])).catch(() => {}); }}
            activeOpacity={0.7}>
            <Text style={[st.accentBtnText, { color: colors.label }]}>Refresh Devices</Text>
          </TouchableOpacity>
        </>
      )}
    </>
  );
}
