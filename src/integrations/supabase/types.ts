export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      canonical_products: {
        Row: {
          active: boolean
          barcode: string | null
          brand: string | null
          category_id: string | null
          created_at: string
          description: string | null
          id: string
          image_url: string | null
          name: string
          quantity: number | null
          unit: string | null
          updated_at: string
        }
        Insert: {
          active?: boolean
          barcode?: string | null
          brand?: string | null
          category_id?: string | null
          created_at?: string
          description?: string | null
          id?: string
          image_url?: string | null
          name: string
          quantity?: number | null
          unit?: string | null
          updated_at?: string
        }
        Update: {
          active?: boolean
          barcode?: string | null
          brand?: string | null
          category_id?: string | null
          created_at?: string
          description?: string | null
          id?: string
          image_url?: string | null
          name?: string
          quantity?: number | null
          unit?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "canonical_products_category_id_fkey"
            columns: ["category_id"]
            isOneToOne: false
            referencedRelation: "categories"
            referencedColumns: ["id"]
          },
        ]
      }
      categories: {
        Row: {
          active: boolean
          created_at: string
          icon: string | null
          id: string
          name: string
          slug: string
        }
        Insert: {
          active?: boolean
          created_at?: string
          icon?: string | null
          id?: string
          name: string
          slug: string
        }
        Update: {
          active?: boolean
          created_at?: string
          icon?: string | null
          id?: string
          name?: string
          slug?: string
        }
        Relationships: []
      }
      cities: {
        Row: {
          active: boolean
          created_at: string
          id: string
          name: string
          slug: string
          state: string
        }
        Insert: {
          active?: boolean
          created_at?: string
          id?: string
          name: string
          slug: string
          state: string
        }
        Update: {
          active?: boolean
          created_at?: string
          id?: string
          name?: string
          slug?: string
          state?: string
        }
        Relationships: []
      }
      current_prices: {
        Row: {
          collected_at: string
          effective_price: number
          id: string
          in_stock: boolean
          price_per_unit: number | null
          promotion_end_at: string | null
          promotion_text: string | null
          promotional_price: number | null
          regular_price: number
          store_product_id: string
          updated_at: string
        }
        Insert: {
          collected_at?: string
          effective_price: number
          id?: string
          in_stock?: boolean
          price_per_unit?: number | null
          promotion_end_at?: string | null
          promotion_text?: string | null
          promotional_price?: number | null
          regular_price: number
          store_product_id: string
          updated_at?: string
        }
        Update: {
          collected_at?: string
          effective_price?: number
          id?: string
          in_stock?: boolean
          price_per_unit?: number | null
          promotion_end_at?: string | null
          promotion_text?: string | null
          promotional_price?: number | null
          regular_price?: number
          store_product_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "current_prices_store_product_id_fkey"
            columns: ["store_product_id"]
            isOneToOne: true
            referencedRelation: "store_products"
            referencedColumns: ["id"]
          },
        ]
      }
      ingestion_runs: {
        Row: {
          error_message: string | null
          finished_at: string | null
          id: string
          products_found: number
          products_updated: number
          started_at: string
          status: Database["public"]["Enums"]["ingestion_status"]
          store_id: string
        }
        Insert: {
          error_message?: string | null
          finished_at?: string | null
          id?: string
          products_found?: number
          products_updated?: number
          started_at?: string
          status?: Database["public"]["Enums"]["ingestion_status"]
          store_id: string
        }
        Update: {
          error_message?: string | null
          finished_at?: string | null
          id?: string
          products_found?: number
          products_updated?: number
          started_at?: string
          status?: Database["public"]["Enums"]["ingestion_status"]
          store_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "ingestion_runs_store_id_fkey"
            columns: ["store_id"]
            isOneToOne: false
            referencedRelation: "stores"
            referencedColumns: ["id"]
          },
        ]
      }
      price_history: {
        Row: {
          collected_at: string
          effective_price: number
          id: string
          in_stock: boolean
          promotional_price: number | null
          regular_price: number
          store_product_id: string
        }
        Insert: {
          collected_at?: string
          effective_price: number
          id?: string
          in_stock?: boolean
          promotional_price?: number | null
          regular_price: number
          store_product_id: string
        }
        Update: {
          collected_at?: string
          effective_price?: number
          id?: string
          in_stock?: boolean
          promotional_price?: number | null
          regular_price?: number
          store_product_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "price_history_store_product_id_fkey"
            columns: ["store_product_id"]
            isOneToOne: false
            referencedRelation: "store_products"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          city: string | null
          city_id: string | null
          created_at: string
          display_name: string | null
          full_name: string | null
          id: string
          updated_at: string
        }
        Insert: {
          city?: string | null
          city_id?: string | null
          created_at?: string
          display_name?: string | null
          full_name?: string | null
          id: string
          updated_at?: string
        }
        Update: {
          city?: string | null
          city_id?: string | null
          created_at?: string
          display_name?: string | null
          full_name?: string | null
          id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "profiles_city_id_fkey"
            columns: ["city_id"]
            isOneToOne: false
            referencedRelation: "cities"
            referencedColumns: ["id"]
          },
        ]
      }
      shopping_list_items: {
        Row: {
          allow_similar_products: boolean
          canonical_product_id: string
          created_at: string
          id: string
          quantity: number
          shopping_list_id: string
          updated_at: string
        }
        Insert: {
          allow_similar_products?: boolean
          canonical_product_id: string
          created_at?: string
          id?: string
          quantity?: number
          shopping_list_id: string
          updated_at?: string
        }
        Update: {
          allow_similar_products?: boolean
          canonical_product_id?: string
          created_at?: string
          id?: string
          quantity?: number
          shopping_list_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "shopping_list_items_canonical_product_id_fkey"
            columns: ["canonical_product_id"]
            isOneToOne: false
            referencedRelation: "canonical_products"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "shopping_list_items_shopping_list_id_fkey"
            columns: ["shopping_list_id"]
            isOneToOne: false
            referencedRelation: "shopping_lists"
            referencedColumns: ["id"]
          },
        ]
      }
      shopping_lists: {
        Row: {
          city_id: string | null
          created_at: string
          id: string
          name: string
          updated_at: string
          user_id: string
        }
        Insert: {
          city_id?: string | null
          created_at?: string
          id?: string
          name?: string
          updated_at?: string
          user_id: string
        }
        Update: {
          city_id?: string | null
          created_at?: string
          id?: string
          name?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "shopping_lists_city_id_fkey"
            columns: ["city_id"]
            isOneToOne: false
            referencedRelation: "cities"
            referencedColumns: ["id"]
          },
        ]
      }
      store_products: {
        Row: {
          active: boolean
          available: boolean
          barcode_raw: string | null
          brand_raw: string | null
          canonical_product_id: string | null
          created_at: string
          external_id: string
          external_name: string
          id: string
          image_url: string | null
          last_seen_at: string | null
          product_url: string | null
          quantity_raw: string | null
          store_id: string
          unit_raw: string | null
          updated_at: string
        }
        Insert: {
          active?: boolean
          available?: boolean
          barcode_raw?: string | null
          brand_raw?: string | null
          canonical_product_id?: string | null
          created_at?: string
          external_id: string
          external_name: string
          id?: string
          image_url?: string | null
          last_seen_at?: string | null
          product_url?: string | null
          quantity_raw?: string | null
          store_id: string
          unit_raw?: string | null
          updated_at?: string
        }
        Update: {
          active?: boolean
          available?: boolean
          barcode_raw?: string | null
          brand_raw?: string | null
          canonical_product_id?: string | null
          created_at?: string
          external_id?: string
          external_name?: string
          id?: string
          image_url?: string | null
          last_seen_at?: string | null
          product_url?: string | null
          quantity_raw?: string | null
          store_id?: string
          unit_raw?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "store_products_canonical_product_id_fkey"
            columns: ["canonical_product_id"]
            isOneToOne: false
            referencedRelation: "canonical_products"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "store_products_store_id_fkey"
            columns: ["store_id"]
            isOneToOne: false
            referencedRelation: "stores"
            referencedColumns: ["id"]
          },
        ]
      }
      stores: {
        Row: {
          active: boolean
          address: string | null
          city_id: string
          created_at: string
          id: string
          last_successful_sync_at: string | null
          logo_url: string | null
          name: string
          slug: string
          updated_at: string
          website_url: string | null
        }
        Insert: {
          active?: boolean
          address?: string | null
          city_id: string
          created_at?: string
          id?: string
          last_successful_sync_at?: string | null
          logo_url?: string | null
          name: string
          slug: string
          updated_at?: string
          website_url?: string | null
        }
        Update: {
          active?: boolean
          address?: string | null
          city_id?: string
          created_at?: string
          id?: string
          last_successful_sync_at?: string | null
          logo_url?: string | null
          name?: string
          slug?: string
          updated_at?: string
          website_url?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "stores_city_id_fkey"
            columns: ["city_id"]
            isOneToOne: false
            referencedRelation: "cities"
            referencedColumns: ["id"]
          },
        ]
      }
      user_roles: {
        Row: {
          created_at: string
          id: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Update: {
          created_at?: string
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      has_role: {
        Args: {
          _role: Database["public"]["Enums"]["app_role"]
          _user_id: string
        }
        Returns: boolean
      }
      immutable_unaccent: { Args: { "": string }; Returns: string }
      list_search_brands: {
        Args: never
        Returns: {
          brand: string
        }[]
      }
      search_canonical_products: {
        Args: { max_results?: number; q: string }
        Returns: {
          active: boolean
          barcode: string | null
          brand: string | null
          category_id: string | null
          created_at: string
          description: string | null
          id: string
          image_url: string | null
          name: string
          quantity: number | null
          unit: string | null
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "canonical_products"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      search_products: {
        Args: {
          brand_filter?: string
          category_slug?: string
          limit_count?: number
          max_price?: number
          min_price?: number
          offset_count?: number
          only_available?: boolean
          only_offers?: boolean
          q?: string
          sort_by?: string
          store_id_filter?: string
        }
        Returns: {
          barcode: string
          brand: string
          category_id: string
          category_name: string
          category_slug: string
          has_promotion: boolean
          id: string
          image_url: string
          last_updated: string
          market_count: number
          max_discount_pct: number
          min_price: number
          name: string
          quantity: number
          reference_price: number
          unit: string
        }[]
      }
    }
    Enums: {
      app_role: "admin" | "user"
      ingestion_status: "running" | "success" | "partial" | "failed"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      app_role: ["admin", "user"],
      ingestion_status: ["running", "success", "partial", "failed"],
    },
  },
} as const
