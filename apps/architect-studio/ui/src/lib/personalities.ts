export const PERSONALITIES = [
    {
        id: 'kenyan_babe',
        name: 'HomeBuddy',
        description: 'Nairobi Gen Z home companion - calm, grounded, minimal',
        emoji: '🏠',
        tags: ['Kenyan', 'Sheng', 'Chill', 'Home Assistant'],
    },
    {
        id: 'sage',
        name: 'Sage',
        description: 'Afro-Caribbean Gen Z therapist - soulful, spicy, emotionally fluent',
        emoji: '🌺',
        tags: ['Therapist', 'Caribbean', 'Healing', 'Unfiltered'],
    },
    {
        id: 'martin',
        name: 'Martin',
        description: 'Systems thinker and builder - technical, strategic, focused',
        emoji: '🛠️',
        tags: ['Builder', 'Systems', 'Technical', 'Strategic'],
    },
];

export const getPersonalityById = (id: string) => {
    return PERSONALITIES.find((p) => p.id === id) || PERSONALITIES[0];
};
