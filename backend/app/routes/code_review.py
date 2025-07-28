from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.db.database import get_db
from app.db.models import CodeSubmission, CodeReview, User
from app.schemas.code import (
    CodeSubmissionCreate,
    CodeSubmissionResponse,
    CodeReviewCreate,
    CodeReviewResponse,
    CodeSubmissionListResponse,
)
from app.routes.auth import get_current_user
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/code-review", tags=["code-review"])


@router.post("/submissions/", response_model=CodeSubmissionResponse)
async def submit_code(
    submission_data: CodeSubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CodeSubmissionResponse:
    """
    Submit code for review by reviewers
    """
    try:
        # logging the incoming data
        logger.info(f"Received submission data: {submission_data}")

        # creating new submission
        db_submission = CodeSubmission(
            session_id=submission_data.session_id,
            # removing file_id as it doesn't exist in the model
            title=submission_data.title,
            description=submission_data.description,
            code_content=submission_data.code_content,
            user_id=current_user.id,  # maps to submitter_id in the response
            status="pending",
        )

        db.add(db_submission)
        await db.commit()
        await db.refresh(db_submission)

        # creating response with submitter_id mapped from user_id
        response = CodeSubmissionResponse(
            id=db_submission.id,
            session_id=db_submission.session_id,
            file_id=submission_data.file_id,
            title=db_submission.title,
            description=db_submission.description,
            code_content=db_submission.code_content,
            submitter_id=db_submission.user_id,  # maps user_id to submitter_id
            status=db_submission.status,
            created_at=db_submission.created_at,
            updated_at=db_submission.updated_at,
        )

        logger.info(f"Code submitted for review by user {current_user.id}: {submission_data.title}")
        return response

    except Exception as e:
        logger.error(f"Failed to submit code for review: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit code for review",
        )


@router.get("/submissions/", response_model=List[CodeSubmissionListResponse])
async def get_submissions(
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[CodeSubmissionListResponse]:
    """
    Get code submissions for review (for reviewers) or user's own submissions
    """
    try:
        # checking if user is a reviewer
        is_reviewer = current_user.role == "reviewer"

        query = select(CodeSubmission).order_by(desc(CodeSubmission.created_at))

        if is_reviewer:
            if status_filter:
                # comma-separated status filters
                if "," in status_filter:
                    statuses = status_filter.split(",")
                    query = query.where(CodeSubmission.status.in_(statuses))
                else:
                    query = query.where(CodeSubmission.status == status_filter)
        else:
            # attempters can only see their own submissions
            query = query.where(CodeSubmission.user_id == current_user.id)
            if status_filter:
                # comma-separated status filters
                if "," in status_filter:
                    statuses = status_filter.split(",")
                    query = query.where(CodeSubmission.status.in_(statuses))
                else:
                    query = query.where(CodeSubmission.status == status_filter)

        result = await db.execute(query)
        submissions = result.scalars().all()

        # creating response objects to map user_id to submitter_id
        response_submissions = []
        for submission in submissions:
            response_submissions.append(
                CodeSubmissionListResponse(
                    id=submission.id,
                    title=submission.title,
                    description=submission.description,
                    submitter_id=submission.user_id,  # mapping user_id to submitter_id
                    status=submission.status,
                    created_at=submission.created_at,
                    code_content=submission.code_content,  # include code content
                )
            )

        logger.info(
            f"Retrieved {len(response_submissions)} submissions for user {current_user.id} (reviewer: {is_reviewer})"
        )
        return response_submissions

    except Exception as e:
        logger.error(f"Failed to get submissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve submissions",
        )


@router.get("/submissions/{submission_id}", response_model=CodeSubmissionResponse)
async def get_submission(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CodeSubmissionResponse:
    """
    Get a specific code submission
    """
    try:
        query = select(CodeSubmission).where(CodeSubmission.id == submission_id)

        # checking access perms
        if current_user.role != "reviewer":
            query = query.where(CodeSubmission.user_id == current_user.id)

        result = await db.execute(query)
        submission = result.scalar_one_or_none()

        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
            )

        # creating response with submitter_id mapped from user_id
        response = CodeSubmissionResponse(
            id=submission.id,
            session_id=submission.session_id,
            file_id=None,  # don't store file_id in the database
            title=submission.title,
            description=submission.description,
            code_content=submission.code_content,
            submitter_id=submission.user_id,  # mapping user_id to submitter_id
            status=submission.status,
            created_at=submission.created_at,
            updated_at=submission.updated_at,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get submission {submission_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve submission",
        )


@router.post("/submissions/{submission_id}/reviews/", response_model=CodeReviewResponse)
async def submit_review(
    submission_id: int,
    review_data: CodeReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CodeReviewResponse:
    """
    Submit a review for a code submission (reviewers only)
    """
    try:
        # checking if user is a reviewer
        if current_user.role != "reviewer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Only reviewers can submit reviews"
            )

        # checking if submission exists
        submission_result = await db.execute(
            select(CodeSubmission).where(CodeSubmission.id == submission_id)
        )
        submission = submission_result.scalar_one_or_none()

        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
            )

        # checking if reviewer already reviewed this submission
        existing_review = await db.execute(
            select(CodeReview).where(
                and_(
                    CodeReview.submission_id == submission_id,
                    CodeReview.reviewer_id == current_user.id,
                )
            )
        )

        if existing_review.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already reviewed this submission",
            )

        # creating new review with basic fields
        db_review = CodeReview(
            submission_id=submission_id,
            reviewer_id=current_user.id,
            status=review_data.status,
            comments=review_data.comments,
        )

        try:
            db_review.feedback = review_data.feedback
        except Exception:
            logger.warning("Could not set feedback field")

        try:
            db_review.quality_before_edits = review_data.quality_before_edits
        except Exception:
            logger.warning("Could not set quality_before_edits field")

        try:
            db_review.quality_after_edits = review_data.quality_after_edits
        except Exception:
            logger.warning("Could not set quality_after_edits field")

        try:
            db_review.edits_made = review_data.edits_made
        except Exception:
            logger.warning("Could not set edits_made field")

        try:
            db_review.is_customer_ready = review_data.is_customer_ready
        except Exception:
            logger.warning("Could not set is_customer_ready field")

        db.add(db_review)

        # updating submission status if it's approved or rejected
        if review_data.status in ["approved", "rejected"]:
            submission.status = review_data.status

        await db.commit()
        await db.refresh(db_review)

        logger.info(
            f"Review submitted by reviewer {current_user.id} for submission {submission_id}: {review_data.status}"
        )

        # creating response manually
        response = CodeReviewResponse(
            id=db_review.id,
            submission_id=db_review.submission_id,
            reviewer_id=db_review.reviewer_id,
            status=db_review.status,
            comments=db_review.comments,
            feedback=getattr(db_review, "feedback", None),
            quality_before_edits=getattr(db_review, "quality_before_edits", None),
            quality_after_edits=getattr(db_review, "quality_after_edits", None),
            edits_made=getattr(db_review, "edits_made", None),
            is_customer_ready=getattr(db_review, "is_customer_ready", None),
            created_at=db_review.created_at,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit review: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to submit review"
        )


@router.get("/submissions/{submission_id}/reviews/", response_model=List[CodeReviewResponse])
async def get_submission_reviews(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[CodeReviewResponse]:
    """
    Get all reviews for a specific submission
    """
    try:
        # chjecking if user has access to this submission
        submission_query = select(CodeSubmission).where(CodeSubmission.id == submission_id)

        if current_user.role != "reviewer":
            submission_query = submission_query.where(CodeSubmission.user_id == current_user.id)

        submission_result = await db.execute(submission_query)
        submission = submission_result.scalar_one_or_none()

        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
            )

        # getting all reviews for this submission
        reviews_result = await db.execute(
            select(CodeReview)
            .where(CodeReview.submission_id == submission_id)
            .order_by(desc(CodeReview.created_at))
        )

        reviews = reviews_result.scalars().all()

        # creating response manually
        response_reviews = []
        for review in reviews:
            response_reviews.append(
                CodeReviewResponse(
                    id=review.id,
                    submission_id=review.submission_id,
                    reviewer_id=review.reviewer_id,
                    status=review.status,
                    comments=review.comments,
                    feedback=getattr(review, "feedback", None),
                    quality_before_edits=getattr(review, "quality_before_edits", None),
                    quality_after_edits=getattr(review, "quality_after_edits", None),
                    edits_made=getattr(review, "edits_made", None),
                    is_customer_ready=getattr(review, "is_customer_ready", None),
                    created_at=review.created_at,
                )
            )

        return response_reviews

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get reviews for submission {submission_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve reviews"
        )


@router.patch("/submissions/{submission_id}/status")
async def update_submission_status(
    submission_id: int,
    new_status: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update submission status (reviewers only)
    """
    try:
        if current_user.role != "reviewer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only reviewers can update submission status",
            )

        if new_status not in ["pending", "approved", "rejected", "revision_requested"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")

        submission_result = await db.execute(
            select(CodeSubmission).where(CodeSubmission.id == submission_id)
        )
        submission = submission_result.scalar_one_or_none()

        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
            )

        submission.status = new_status
        await db.commit()

        logger.info(
            f"Submission {submission_id} status updated to {new_status} by reviewer {current_user.id}"
        )
        return {"message": "Status updated successfully", "status": new_status}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update submission status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update submission status",
        )
