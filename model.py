import datetime
import enum
from typing import List, Optional
from datetime import date
from sqlalchemy import Boolean, Integer, String, DateTime, ForeignKey, CheckConstraint, Numeric, Date, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from . import db
import flask_login
from pathlib import Path
import pathlib
from sqlalchemy.orm.attributes import flag_modified


from flask import current_app


class ProposalStatus(enum.Enum):
    proposed = 1
    accepted = 2
    rejected = 3
    ignored = 4
    reschedule = 5


class SexualOrentation(enum.Enum):
    Man = 1
    Woman = 2
    Both = 3


class LikingAssociation(db.Model):
    __tablename__ = 'liking_association'
    user_likes_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"), primary_key=True)
    likes_user_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"), primary_key=True)


class BlockedAssociation(db.Model):
    __tablename__ = 'blocked_association'
    user_blocks_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"), primary_key=True)
    user_is_blocked_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"), primary_key=True)


class Chat(db.Model): 
    id: Mapped[int] = mapped_column(primary_key=True)
    user1_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"))
    user1: Mapped["User"] = relationship(foreign_keys=[user1_id])
    user2_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"))
    user2: Mapped["User"] = relationship(foreign_keys=[user2_id])
    texts: Mapped[Optional[List["Text"]]] = relationship(back_populates="chat") 


class Photo(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    file_extension: Mapped[str] = mapped_column(String(8))
    profile_id: Mapped[int] = mapped_column(ForeignKey("user_profile.user_id"))
    is_photo_profile: Mapped[bool] = mapped_column(Boolean, default=False) 
    is_default: Mapped[bool] = mapped_column(Boolean, default=True) 
    profile: Mapped["UserProfile"] = relationship(back_populates="photos")

    def photo_filename(photo):
        path = (
            pathlib.Path(current_app.root_path)
            / "static"
            / "photos"
            / f"photo-{photo.id}.{photo.file_extension}"
        )
        return path


class UserProfile(db.Model):
    __tablename__ = 'user_profile'
    user_id: Mapped[int] = mapped_column(ForeignKey('user.user_id'), primary_key=True)
    user: Mapped["User"] = relationship(back_populates="user_profile")
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    gender: Mapped["SexualOrentation"] 
    
    birthday : Mapped[date] = mapped_column(Date, nullable=False)
    description : Mapped[Optional[str]] = mapped_column(String(64))
    
    photos: Mapped[Optional[List["Photo"]]] = relationship(back_populates="profile")  
    
    matching_preferences: Mapped["MatchingPreferences"] = relationship(back_populates="user_profile")

    sent_proposals: Mapped[List["DateProposal"]] = relationship(
        back_populates="sender_profile", foreign_keys="[DateProposal.sender_id]"
    )
    received_proposals: Mapped[List["DateProposal"]] = relationship(
        back_populates="receiver_profile", foreign_keys="[DateProposal.receiver_id]"
    )


class User(flask_login.UserMixin, db.Model):
    user_id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(128), unique=True)
    password_salt: Mapped[str] = mapped_column(String(256), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(String(256), nullable=False)
    user_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    
    user_profile: Mapped["UserProfile"] = relationship(back_populates="user")
 
    user_likes: Mapped[List["User"]] = relationship(
        secondary=LikingAssociation.__table__,
        primaryjoin=LikingAssociation.user_likes_id == user_id,
        secondaryjoin=LikingAssociation.likes_user_id == user_id,
        back_populates="likes_user",
    )

    likes_user: Mapped[List["User"]] = relationship(
        secondary=LikingAssociation.__table__,
        primaryjoin=LikingAssociation.likes_user_id == user_id,
        secondaryjoin=LikingAssociation.user_likes_id == user_id,
        back_populates="user_likes",
    )

    user_blocks: Mapped[List["User"]] = relationship(
        secondary=BlockedAssociation.__table__,
        primaryjoin=BlockedAssociation.user_blocks_id == user_id,
        secondaryjoin=BlockedAssociation.user_is_blocked_id == user_id,
        back_populates="user_is_blocked",
    )

    user_is_blocked: Mapped[List["User"]] = relationship(
        secondary=BlockedAssociation.__table__,
        primaryjoin=BlockedAssociation.user_is_blocked_id == user_id,
        secondaryjoin=BlockedAssociation.user_blocks_id == user_id,
        back_populates="user_blocks",
    )
  
    def get_id(self):
        return self.user_id

  
class DateProposal(db.Model):
    __tablename__ = 'date_proposal'
    id: Mapped[int] = mapped_column(primary_key=True)
    date_day: Mapped[date] = mapped_column(Date)
    status: Mapped["ProposalStatus"]
    timestamp_proposal: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    timestamp_answer: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    opt_text_message: Mapped[Optional[str]] = mapped_column(String(128))
    opt_text_response: Mapped[Optional[str]] = mapped_column(String(128))

    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurant.id"))
    restaurant: Mapped["Restaurant"] = relationship(back_populates="proposals")

    sender_id: Mapped[int] = mapped_column(ForeignKey("user_profile.user_id"))
    sender_profile: Mapped["UserProfile"] = relationship(
        back_populates="sent_proposals", foreign_keys=[sender_id]
    )

    receiver_id: Mapped[int] = mapped_column(ForeignKey("user_profile.user_id"))
    receiver_profile: Mapped["UserProfile"] = relationship(
        back_populates="received_proposals", foreign_keys=[receiver_id]
    )


class Restaurant(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    
    proposals: Mapped[Optional[List["DateProposal"]]] = relationship(back_populates="restaurant")

    def is_fully_booked(self, date: date) -> bool:
        """Check if a restaurant is fully booked in a proposed date"""
        booked_count = db.session.query(DateProposal).filter(
            DateProposal.restaurant_id == self.id,
            DateProposal.date_day == date,
            DateProposal.status.in_([
                ProposalStatus.proposed,
                ProposalStatus.accepted,
                ProposalStatus.ignored,
                ProposalStatus.reschedule
            ])  # Reservations for all date status except for 'rejected'
        ).count()
        return booked_count >= self.capacity

    
class MatchingPreferences(db.Model):
    __tablename__ = 'matching_preferences'
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.user_id"), primary_key=True)
    user_profile: Mapped["UserProfile"] = relationship(back_populates="matching_preferences")
    gender_interests: Mapped["SexualOrentation"] 
    lower_age_range: Mapped[float] = mapped_column(Numeric(3, 0))
    higher_age_range : Mapped[float] = mapped_column(Numeric(3, 0))

    def get_id(self):
        return self.user_id


class Text(db.Model):
    __tablename__ = "text"
    id: Mapped[int] = mapped_column(primary_key=True)  
    chat_id: Mapped[int] = mapped_column(ForeignKey("chat.id"))  
    chat: Mapped["Chat"] = relationship(back_populates="texts")
    sender_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"))
    sender: Mapped["User"] = relationship()
    text: Mapped[str] = mapped_column(String(254))
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )