import type { FC } from "react";

interface Props {
  userRole: string;
  openProgressShopId: number | null;
}

export const ReviewManagementWidget: FC<Props> = ({ userRole, openProgressShopId }) => {
  return (
    <div data-testid="review-management-stub">
      <p className="text-[14px] text-muted">Reviews widget — implementation in Plan 10.</p>
    </div>
  );
};
