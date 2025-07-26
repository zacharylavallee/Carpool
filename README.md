# Carpool Bot 🚗

A Slack bot for organizing carpools and ride-sharing within private channels and direct messages.

## Features

### 🚗 Trip & Car Management
- **Create Trips**: Organize carpools for specific events or destinations
- **Create Cars**: Set up vehicles with customizable seat counts
- **Join Requests**: Interactive approval system for joining cars
- **Smart Cleanup**: Cars are automatically deleted when the owner leaves

### 👥 Member Management
- **Join Cars**: Request to join available cars with approval workflow
- **Leave Cars**: Exit cars with automatic cleanup for car owners
- **Boot Members**: Car owners can remove members from their cars
- **Member Tracking**: Real-time tracking of car occupancy

### 🔒 Security & Privacy
- **Private Channel Only**: Bot only works in private channels and DMs to prevent spam
- **Owner Permissions**: Only car/trip creators can modify or delete their items
- **Confirmation Dialogs**: Safety confirmations for destructive actions
- **Database Integrity**: Robust foreign key constraints and data validation

### 📊 Information Commands
- **List Cars**: View all available cars for a trip
- **Help**: Interactive help system with command documentation
- **Status Updates**: Real-time announcements for all carpool activities

## Commands

### Trip Management
- `/trip TripName` - Create or update a trip for the current channel

### Car Management
- `/car CarName seats` - Create a new car (e.g., `/car "John's Honda" 4`)
- `/update seats` - Update seat count for your car
- `/delete` - Delete your car (with confirmation)
- `/list` - List all cars for the current trip

### Member Management
- `/in CarID` - Request to join a car
- `/out` - Leave your current car
- `/boot @user` - Remove a member from your car (owners only)

### Information
- `/help` - Show available commands and usage
- `/trips` - List all trips across channels

## Installation

### Prerequisites
- Python 3.8+
- PostgreSQL database
- Slack workspace with bot permissions

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Carpool
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Configuration**
   Create a `.env` file with:
   ```env
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   SLACK_SIGNING_SECRET=your-signing-secret
   DATABASE_URL=postgresql://user:password@host:port/database
   ```

4. **Database Setup**
   ```bash
   python -c "from config.database import setup_database; setup_database()"
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

## Slack App Configuration

### Required Bot Token Scopes
- `app_mentions:read`
- `channels:read`
- `chat:write`
- `commands`
- `users:read`

### Required User Token Scopes
- `channels:read`
- `users:read`

### Slash Commands
Configure these slash commands in your Slack app:
- `/trip` - Create/manage trips
- `/car` - Create cars
- `/in` - Join cars
- `/out` - Leave cars
- `/boot` - Remove members
- `/update` - Update car details
- `/delete` - Delete cars
- `/list` - List cars
- `/help` - Show help
- `/trips` - List all trips

### Event Subscriptions
- Request URL: `https://your-domain.com/slack/events`

## Database Management

The `db_scripts/` folder contains essential database tools:

- **`validate_database.py`** - Comprehensive database health checks
- **`reset_database.py`** - Clean database reset for development
- **`db_sync_checker.py`** - Schema synchronization analysis
- **`fix_database_schema.py`** - Database migration and fixes

See `db_scripts/README.md` for detailed usage instructions.

## Project Structure

```
/Carpool/
├── app.py                    # Main Flask application
├── commands/                 # Slash command handlers
│   ├── car.py               # Car creation and listing
│   ├── help.py              # Help system
│   ├── manage.py            # Car updates and deletion
│   ├── member.py            # Member management
│   ├── trip.py              # Trip management
│   └── user.py              # User utilities
├── config/                   # Configuration
│   └── database.py          # Database setup and connection
├── middleware/               # Request middleware
│   └── channel_restrictions.py # Private channel enforcement
├── utils/                    # Utility functions
│   ├── channel_guard.py     # Channel access validation
│   └── helpers.py           # Common helper functions
├── db_scripts/              # Database management tools
└── requirements.txt         # Python dependencies
```

## Usage Examples

### Creating a Trip and Car
```
/trip "Beach Trip 2024"
/car "Sarah's SUV" 7
```

### Joining a Car
```
/list                    # See available cars
/in 1                    # Request to join car ID 1
```

### Managing Your Car
```
/update 5                # Change to 5 seats
/boot @john             # Remove john from your car
/delete                 # Delete your car (with confirmation)
```

## Deployment

### Local Development
```bash
python app.py
```

### Production Deployment
1. Set up your production database
2. Configure environment variables
3. Run database validation: `python db_scripts/validate_database.py`
4. Deploy using your preferred method (Heroku, AWS, etc.)

### Health Checks
- Database validation: `python db_scripts/validate_database.py`
- Schema sync check: `python db_scripts/db_sync_checker.py`

## Security Features

- **Private Channel Enforcement**: Bot only works in private channels and DMs
- **Owner-Only Permissions**: Users can only modify their own cars and trips
- **Confirmation Dialogs**: Destructive actions require explicit confirmation
- **Database Constraints**: Foreign key relationships prevent orphaned data
- **Input Validation**: All user inputs are sanitized and validated

## Troubleshooting

### Common Issues

1. **"Bot not in channel" errors**
   - Ensure the bot is added to the private channel
   - Check bot permissions in Slack app settings

2. **Database connection errors**
   - Verify `DATABASE_URL` in environment variables
   - Run `python db_scripts/validate_database.py` to check database health

3. **Command not responding**
   - Check Slack app slash command configuration
   - Verify request URL is accessible
   - Check application logs for errors

### Getting Help

1. Use `/help` command in Slack for usage instructions
2. Run database validation scripts for database issues
3. Check application logs for detailed error information

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run database validation tests
5. Submit a pull request

## License

[Add your license information here]

## Support

For issues and questions:
- Check the troubleshooting section above
- Run diagnostic scripts in `db_scripts/`
- Review application logs for detailed error information
