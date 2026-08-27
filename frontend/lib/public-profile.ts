import type { CatalogItem } from "./api";
import type { Review } from "./community";

export interface PublicProfileCollection {
  name: string;
  slug: string;
  description: string;
  item_count: number;
  preview_titles: CatalogItem[];
  updated_at: string;
}

export interface PublicProfileData {
  profile: {
    public_id: string;
    display_name: string;
    bio: string;
  };
  stats: {
    collections: number;
    reviews: number;
    followers: number;
  };
  collections: PublicProfileCollection[];
  reviews: Review[];
}
