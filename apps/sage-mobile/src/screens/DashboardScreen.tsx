
import React from "react";
import { StyleSheet, Text, View, ScrollView } from "react-native";
import { GlassCard } from "../components/ui/GlassCard";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { COLORS, SPACING, RADIUS } from "../constants/theme";
import { Bell, Sun, Cloud, Music } from "lucide-react-native";

export function DashboardScreen() {
    return (
        <ScreenLayout>
            <ScrollView contentContainerStyle={styles.scroll}>
                {/* Header */}
                <View style={styles.header}>
                    <View>
                        <Text style={styles.greeting}>Good Evening</Text>
                        <Text style={styles.date}>
                            {new Date().toLocaleDateString(undefined, {
                                weekday: "long",
                                month: "long",
                                day: "numeric",
                            })}
                        </Text>
                    </View>
                    <GlassCard style={styles.profileButton}>
                        <Bell size={20} color={COLORS.text.primary} />
                    </GlassCard>
                </View>

                {/* Widgets Grid */}
                <View style={styles.grid}>
                    {/* Weather / Status */}
                    <GlassCard style={styles.weatherCard}>
                        <View style={styles.row}>
                            <Cloud size={24} color={COLORS.accent.primary} />
                            <Text style={styles.temp}>24°C</Text>
                        </View>
                        <Text style={styles.weatherDesc}>Partly Cloudy</Text>
                        <Text style={styles.location}>Jakarta, Indonesia</Text>
                    </GlassCard>

                    {/* System Status */}
                    <GlassCard style={styles.systemCard}>
                        <View style={styles.row}>
                            <Sun size={24} color={COLORS.accent.warning} />
                            <Text style={styles.cardTitle}>System</Text>
                        </View>
                        <Text style={styles.statusText}>All Systems Nominal</Text>
                    </GlassCard>
                </View>

                {/* Smart Home Controls (Mock) */}
                <Text style={styles.sectionTitle}>Smart Home</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.horizontalScroll}>
                    <GlassCard style={styles.smartCard}>
                        <Text style={styles.cardTitle}>Living Room</Text>
                        <Text style={styles.subText}>Lights On</Text>
                    </GlassCard>
                    <GlassCard style={styles.smartCard}>
                        <Text style={styles.cardTitle}>CCTV</Text>
                        <Text style={styles.subText}>Active</Text>
                    </GlassCard>
                    <GlassCard style={styles.smartCard}>
                        <Text style={styles.cardTitle}>Thermostat</Text>
                        <Text style={styles.subText}>22°C</Text>
                    </GlassCard>
                </ScrollView>

                {/* Media Player (Mock) */}
                <Text style={styles.sectionTitle}>Now Playing</Text>
                <GlassCard style={styles.mediaCard}>
                    <View style={styles.row}>
                        <View style={styles.albumArt}>
                            <Music size={20} color={COLORS.text.tertiary} />
                        </View>
                        <View>
                            <Text style={styles.songTitle}>Starlight</Text>
                            <Text style={styles.artist}>Muse</Text>
                        </View>
                    </View>
                </GlassCard>

            </ScrollView>
        </ScreenLayout>
    );
}

const styles = StyleSheet.create({
    scroll: {
        paddingBottom: 100,
    },
    header: {
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "center",
        marginTop: SPACING.l,
        marginBottom: SPACING.xl,
    },
    greeting: {
        fontSize: 28,
        fontWeight: "bold",
        color: COLORS.text.primary,
    },
    date: {
        fontSize: 14,
        color: COLORS.text.secondary,
        marginTop: 4,
    },
    profileButton: {
        padding: SPACING.s,
        borderRadius: RADIUS.full,
    },
    grid: {
        flexDirection: "row",
        gap: SPACING.m,
        marginBottom: SPACING.l,
    },
    weatherCard: {
        flex: 1,
        height: 140,
        justifyContent: "space-between",
    },
    systemCard: {
        flex: 1,
        height: 140,
        justifyContent: "space-between",
    },
    row: {
        flexDirection: "row",
        alignItems: "center",
        gap: SPACING.s,
    },
    temp: {
        fontSize: 24,
        fontWeight: "bold",
        color: COLORS.text.primary,
    },
    weatherDesc: {
        fontSize: 14,
        color: COLORS.text.secondary,
    },
    location: {
        fontSize: 12,
        color: COLORS.text.tertiary,
    },
    cardTitle: {
        fontSize: 16,
        fontWeight: "600",
        color: COLORS.text.primary,
    },
    statusText: {
        fontSize: 14,
        color: COLORS.accent.success,
    },
    sectionTitle: {
        fontSize: 18,
        fontWeight: "bold",
        color: COLORS.text.primary,
        marginBottom: SPACING.m,
        marginTop: SPACING.m,
    },
    horizontalScroll: {
        overflow: "visible",
        marginHorizontal: -SPACING.m, // negative margin to allow scroll to edge
        paddingHorizontal: SPACING.m,
    },
    smartCard: {
        width: 120,
        height: 120,
        marginRight: SPACING.m,
        justifyContent: "space-between",
    },
    subText: {
        fontSize: 12,
        color: COLORS.text.secondary,
    },
    mediaCard: {
        flexDirection: "row",
        alignItems: "center",
    },
    albumArt: {
        width: 40,
        height: 40,
        borderRadius: 8,
        backgroundColor: "rgba(255,255,255,0.1)",
        alignItems: "center",
        justifyContent: "center",
    },
    songTitle: {
        fontSize: 16,
        fontWeight: "600",
        color: COLORS.text.primary,
    },
    artist: {
        fontSize: 12,
        color: COLORS.text.secondary,
    },
});
