import type { Conversation } from '../types/conversation'

// Placeholder data until the backend exposes a conversations API.
export const mockConversations: Conversation[] = [
  {
    id: '1',
    title: 'Analyse du fichier ventes Q3',
    messages: [
      { id: 'm1', role: 'user', content: 'Peux-tu résumer les tendances de vente du fichier que je viens de charger ?' },
      {
        id: 'm2',
        role: 'assistant',
        content:
          "Bien sûr. D'après le fichier, les ventes ont augmenté de 12% au troisième trimestre, portées principalement par la région Nord. Veux-tu un détail par produit ?",
      },
    ],
  },
  {
    id: '2',
    title: 'Nettoyage des doublons clients',
    messages: [{ id: 'm3', role: 'user', content: 'Comment supprimer les doublons dans la colonne email ?' }],
  },
  {
    id: '3',
    title: 'Comparatif budgets 2025 vs 2026',
    messages: [],
  },
]
