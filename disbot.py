"""
-------POSSIBLE UPDATES IN THE FUTURE-------
 - allow user to input canvas token and get everyone's data indivisually
    - possibly requires knowledge for temp storing all the data and passing it to firestore in one go
 - have all assignment and course IDs as strings to remove additional conversion between int to string and vice versa
"""

# imports for Canvas API calls
import requests

# imports for converting UTC to PST
from datetime import datetime
import pytz

# imports for firestore database
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# imports for discord bot
import discord
from discord import app_commands

# scheduling daily update
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# tokens
firebase_token = "###########"
canvas_token = "###########"
discord_token = "###########"

# handling database
cred = credentials.Certificate(firebase_token)
firebase_admin.initialize_app(cred)
db = firestore.client()

# handling canvas API
base_url = "https://sdccd.instructure.com/api/v1"
todo_path = "/users/self/todo"
endpoint = f"{base_url}{todo_path}?access_token={canvas_token}"

# basic example for scheduling task (check line 66)
def daily_schedule():
    update_assignments()


# Making slash commands for discord (source: https://www.youtube.com/watch?v=PgN9U1wBTAg&ab_channel=Digiwind)
class aclient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.synced = False
        self.scheduler = AsyncIOScheduler()

    async def on_ready(self):
        await self.wait_until_ready()

        # schedules the specified fuction to run every minute (when the clock hour hits 00)
        self.scheduler.add_job(daily_schedule, CronTrigger(hour=0))
        self.scheduler.start()

        if not self.synced:
            await tree.sync(guild=discord.Object(id=459419296502906890))

client = aclient()
tree = app_commands.CommandTree(client)

@tree.command(name="list_courses", description="List available courses.", guild=discord.Object(id=459419296502906890))
async def listCourses(interaction: discord.Interaction):
    embed = discord.Embed(title='Course List', color=discord.Color.dark_magenta())

    # retrives course names from firestore database and adds to embed
    courses = db.collection(u'courses').stream()
    course_idx = 0
    for course in courses:
        course_title = course.to_dict().get('course_name')
        embed.add_field(name=f"{str(course_idx)} : {course_title}", value="\u200b", inline=False)
        course_idx+=1

    await interaction.response.send_message(embed=embed)

@tree.command(name="add_course", description="Adds a course to your account. Use a number correlating in list_courses", guild=discord.Object(id=459419296502906890))
async def addCourse(interaction: discord.Interaction, course_idx: int):
    # check if user is in data base, add them if not
    user = db.collection(u'users').document(str(interaction.user.id)).get()
    user_data = db.collection(u'users').document(str(interaction.user.id))
    if not user.exists:
        data = {
            u'enrolled_courses': [],
            u'workload': []
        }

        user_data.set(data)

    available_courses = [course.id for course in db.collection(u'courses').stream()]
    user_data.update({u'enrolled_courses': firestore.ArrayUnion([int(available_courses[course_idx])])})

    await interaction.response.send_message(f"The following course has been added: {db.collection(u'courses').document(available_courses[course_idx]).get().to_dict().get('course_name')}")

@tree.command(name="remove_course", description="Removes a course from your account", guild=discord.Object(id=459419296502906890))
async def removeCourse(interaction: discord.Interaction, course_idx: int):
    user_data = db.collection(u'users').document(str(interaction.user.id))
    user_courses = db.collection(u'users').document(str(408820352479920130)).get().to_dict().get('enrolled_courses')

    if course_idx in range(0, len(user_courses)):
        user_data.update({u'enrolled_courses': firestore.ArrayRemove([int(user_courses[course_idx])])})
        await interaction.response.send_message(f"The course has been removed.")
    else:
        await interaction.response.send_message(f"OutOfBounds Error: Pick a number correlating to your course list.")

@tree.command(name="my_courses", description="Displays courses added on your account", guild=discord.Object(id=459419296502906890))
async def userCourses(interaction: discord.Interaction):
    user_courses = db.collection(u'users').document(str(interaction.user.id)).get().to_dict().get('enrolled_courses')
    embed = discord.Embed(title='Your Courses', color=discord.Color.dark_teal())
    idx = 0
    for course_ID in user_courses:
        embed.add_field(name=f"{str(idx)} : {db.collection(u'courses').document(str(course_ID)).get().to_dict().get('course_name')}", value="\u200b", inline=False)
        idx += 1

    await interaction.response.send_message(embed=embed)

@tree.command(name="workload", description="Check your workload", guild=discord.Object(id=459419296502906890))
async def listAssignments(interaction: discord.Interaction):
    embed = discord.Embed(title='Workload', color=discord.Color.orange())

    workload = db.collection(u'users').document(str(interaction.user.id)).get().to_dict().get("workload")
    idx = 0
    for assignment in workload:
        assignment_data = db.collection(u'assignments').document(str(assignment)).get().to_dict()
        course_name = db.collection(u'courses').document(str(assignment_data.get("course_ID"))).get().to_dict().get("course_name")
        assignment_title = assignment_data.get("assignment_title")
        due_date = datetime.fromtimestamp( (assignment_data.get("due_date")).timestamp() ).strftime("%m/%d")
        embed.add_field(name=f"{str(idx)} : {assignment_title} - {course_name}", value=f"Due date: {due_date}", inline=False)
        idx += 1

    await interaction.response.send_message(embed=embed)

@tree.command(name="done", description="Remove an assignment from your workload", guild=discord.Object(id=459419296502906890))
async def markFinished(interaction: discord.Interaction, assignment_idx: int):
    workload = db.collection(u'users').document(str(interaction.user.id)).get().to_dict().get("workload")
    if assignment_idx in range(0, len(workload)):
        db.collection(u'users').document(str(interaction.user.id)).update({u'workload': firestore.ArrayRemove([workload[assignment_idx]])})
        await interaction.response.send_message("Successfully removed task off of workload.")
    else:
        await interaction.response.send_message("OutOfBounds Error: Pick a number correlating to your assignment list.")
    pass

@tree.command(name="update_due", description="Gloablly updates the due date for a listed assignment", guild=discord.Object(id=459419296502906890))
async def addCourse(interaction: discord.Interaction, assignment_idx: int, month_int: int, day_int: int):
    workload = db.collection(u'users').document(str(interaction.user.id)).get().to_dict().get("workload")
    if assignment_idx in range(0, len(workload)):
        assignment_ID = workload[assignment_idx]
        orig_due =  datetime.fromtimestamp( (db.collection(u'assignments').document(str(assignment_ID)).get().to_dict().get("due_date")).timestamp() )
        new_due = orig_due.replace(month=month_int, day=day_int)
        db.collection(u'assignments').document(str(assignment_ID)).update({u'due_date': new_due})
        await interaction.response.send_message(f"Due date successfully updated to {month_int}/{day_int}.")
    else:
        await interaction.response.send_message("OutOfBounds Error: Pick a number correlating to your assignment list.")

@tree.command(name="say", guild=discord.Object(id=459419296502906890))
async def say(interaction: discord.Interaction, msg: str):
    await interaction.response.send_message(f"mf named {interaction.user} with the discord id {interaction.user.id} out here saying {msg} lmao fuq outta here")

@tree.command(name="update_assignments", description="Refreshes with upcoming assignments and removes past ones.", guild=discord.Object(id=459419296502906890))
async def update(interaction: discord.Interaction):
    update_assignments()
    await interaction.response.send_message("Assignments list successfully updated.")

def update_assignments():
    r = requests.get(endpoint)

    # updates firestore database with new assignments
    if r.status_code in range(200,299):
        data = r.json()

        for task in data:
            course_ID = task['course_id']
            assignment_ID = task['assignment']['id']

            # if assignment is already in database, skip to next iteration
            if ( db.collection(u'assignments').document(str(assignment_ID)).get() ).exists:
                continue

            assignment_title = task['assignment']['name']
            due_date = pytz.timezone('UTC').localize(datetime.strptime(task['assignment']['due_at'], "%Y-%m-%dT%H:%M:%SZ"))

            data = {
                u'course_ID': course_ID,
                u'assignment_title': assignment_title,
                u'due_date': due_date
            }

            db.collection(u'assignments').document(str(assignment_ID)).set(data)

            # add assignments to user workloads part of the course as well
            users = db.collection(u'users').where(u'enrolled_courses', u'array_contains', int(course_ID)).stream()
            for user in users:
                db.collection(u'users').document(user.id).update({u'workload': firestore.ArrayUnion([assignment_ID])})

    # removes old assignments from the database
    assignments = db.collection(u'assignments').stream()

    # timetuple().tm_yday returns the current day relative to the Jan 1st (000)
    current_day =  int( datetime.now(pytz.utc).timetuple().tm_yday )
    for assignment in assignments:
        # removes assignment if due_date has passed by 2 days
        if ( int( assignment.to_dict().get('due_date').timetuple().tm_yday ) - current_day ) <= -3:

            # IF DATABASE>>USERS>>WORKLOAD CONTAINS {assignment.id}
                # REMOVE THE ASSINGMENT FROM THE WORKLOAD
            users = db.collection(u'users').where(u'workload', u'array_contains', assignment.id).stream()

            for user in users:
                db.collection(u'users').document(user.id).update({u'workload': firestore.ArrayRemove([int(assignment.id)])})

            # remove assignment from assignments collection
            db.collection(u'assignments').document(assignment.id).delete()

client.run(discord_token)
