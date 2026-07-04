#!/usr/bin/env python3
"""
Contact Book Management System
A simple and elegant contact management application with a beautiful terminal UI.
"""

import json
import os
from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich import box

console = Console()

# File to store contacts
CONTACTS_FILE = "contacts.json"


def load_contacts() -> List[Dict[str, str]]:
    """Load contacts from JSON file."""
    if os.path.exists(CONTACTS_FILE):
        try:
            with open(CONTACTS_FILE, 'r', encoding='utf-8') as file:
                contacts = json.load(file)
                return contacts if isinstance(contacts, list) else []
        except (json.JSONDecodeError, IOError):
            console.print("[red]Error: Could not load contacts file. Starting with empty contact list.[/red]")
            return []
    return []


def save_contacts(contacts: List[Dict[str, str]]) -> bool:
    """Save contacts to JSON file."""
    try:
        with open(CONTACTS_FILE, 'w', encoding='utf-8') as file:
            json.dump(contacts, file, indent=4, ensure_ascii=False)
        return True
    except IOError:
        console.print("[red]Error: Could not save contacts to file.[/red]")
        return False


def display_menu():
    """Display the main menu."""
    menu_text = """
[bold cyan]========================================[/bold cyan]
[bold cyan]   CONTACT BOOK MANAGEMENT SYSTEM      [/bold cyan]
[bold cyan]========================================[/bold cyan]

[bold yellow]1.[/bold yellow] Add New Contact
[bold yellow]2.[/bold yellow] Search Contact
[bold yellow]3.[/bold yellow] Update Contact
[bold yellow]4.[/bold yellow] Delete Contact
[bold yellow]5.[/bold yellow] Display All Contacts
[bold yellow]6.[/bold yellow] Exit

[dim]Enter your choice (1-6):[/dim]
"""
    console.print(Panel(menu_text, title="[bold green]Main Menu[/bold green]", border_style="cyan"))


def add_contact(contacts: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Add a new contact to the list."""
    console.print("\n[bold cyan]--- Add New Contact ---[/bold cyan]\n")
    
    name = Prompt.ask("[bold]Enter name[/bold]")
    if not name.strip():
        console.print("[red]Name cannot be empty![/red]")
        return contacts
    
    # Check if contact already exists
    for contact in contacts:
        if contact.get('name', '').lower() == name.lower():
            if not Confirm.ask(f"[yellow]Contact '{name}' already exists. Do you want to update it?[/yellow]"):
                return contacts
            # Update existing contact
            return update_contact_by_name(contacts, name)
    
    phone = Prompt.ask("[bold]Enter phone number[/bold]")
    email = Prompt.ask("[bold]Enter email address[/bold]")
    address = Prompt.ask("[bold]Enter address[/bold]", default="")
    
    new_contact = {
        'name': name.strip(),
        'phone': phone.strip(),
        'email': email.strip(),
        'address': address.strip()
    }
    
    contacts.append(new_contact)
    console.print(f"\n[green][+] Contact '{name}' added successfully![/green]\n")
    return contacts


def search_contact(contacts: List[Dict[str, str]]):
    """Search for a contact by name."""
    console.print("\n[bold cyan]--- Search Contact ---[/bold cyan]\n")
    
    if not contacts:
        console.print("[yellow]No contacts available to search.[/yellow]\n")
        return
    
    search_term = Prompt.ask("[bold]Enter name to search[/bold]")
    if not search_term.strip():
        console.print("[red]Search term cannot be empty![/red]\n")
        return
    
    found_contacts = []
    search_lower = search_term.lower()
    
    for contact in contacts:
        if search_lower in contact.get('name', '').lower():
            found_contacts.append(contact)
    
    if found_contacts:
        display_contacts_table(found_contacts, title="Search Results")
    else:
        console.print(f"[yellow]No contacts found matching '{search_term}'.[/yellow]\n")


def update_contact(contacts: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Update an existing contact."""
    console.print("\n[bold cyan]--- Update Contact ---[/bold cyan]\n")
    
    if not contacts:
        console.print("[yellow]No contacts available to update.[/yellow]\n")
        return contacts
    
    name = Prompt.ask("[bold]Enter the name of the contact to update[/bold]")
    if not name.strip():
        console.print("[red]Name cannot be empty![/red]\n")
        return contacts
    
    return update_contact_by_name(contacts, name)


def update_contact_by_name(contacts: List[Dict[str, str]], name: str) -> List[Dict[str, str]]:
    """Update contact by name."""
    contact_index = None
    for i, contact in enumerate(contacts):
        if contact.get('name', '').lower() == name.lower():
            contact_index = i
            break
    
    if contact_index is None:
        console.print(f"[red]Contact '{name}' not found![/red]\n")
        return contacts
    
    old_contact = contacts[contact_index]
    console.print(f"\n[dim]Current information for '{name}':[/dim]")
    display_contacts_table([old_contact], title="Current Contact")
    
    console.print("\n[bold]Enter new information (press Enter to keep current value):[/bold]\n")
    
    new_name = Prompt.ask(f"[bold]Name[/bold] (current: {old_contact.get('name', '')})", default=old_contact.get('name', ''))
    new_phone = Prompt.ask(f"[bold]Phone[/bold] (current: {old_contact.get('phone', '')})", default=old_contact.get('phone', ''))
    new_email = Prompt.ask(f"[bold]Email[/bold] (current: {old_contact.get('email', '')})", default=old_contact.get('email', ''))
    new_address = Prompt.ask(f"[bold]Address[/bold] (current: {old_contact.get('address', '')})", default=old_contact.get('address', ''))
    
    contacts[contact_index] = {
        'name': new_name.strip(),
        'phone': new_phone.strip(),
        'email': new_email.strip(),
        'address': new_address.strip()
    }
    
    console.print(f"\n[green][+] Contact '{new_name}' updated successfully![/green]\n")
    return contacts


def delete_contact(contacts: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Delete a contact from the list."""
    console.print("\n[bold cyan]--- Delete Contact ---[/bold cyan]\n")
    
    if not contacts:
        console.print("[yellow]No contacts available to delete.[/yellow]\n")
        return contacts
    
    name = Prompt.ask("[bold]Enter the name of the contact to delete[/bold]")
    if not name.strip():
        console.print("[red]Name cannot be empty![/red]\n")
        return contacts
    
    contact_index = None
    for i, contact in enumerate(contacts):
        if contact.get('name', '').lower() == name.lower():
            contact_index = i
            break
    
    if contact_index is None:
        console.print(f"[red]Contact '{name}' not found![/red]\n")
        return contacts
    
    contact_to_delete = contacts[contact_index]
    display_contacts_table([contact_to_delete], title="Contact to Delete")
    
    if Confirm.ask(f"\n[bold red]Are you sure you want to delete '{name}'?[/bold red]"):
        contacts.pop(contact_index)
        console.print(f"\n[green][+] Contact '{name}' deleted successfully![/green]\n")
    else:
        console.print(f"\n[yellow]Deletion cancelled.[/yellow]\n")
    
    return contacts


def display_contacts_table(contacts: List[Dict[str, str]], title: str = "All Contacts"):
    """Display contacts in a beautiful table format."""
    if not contacts:
        console.print(f"[yellow]No contacts to display.[/yellow]\n")
        return
    
    table = Table(title=title, show_header=True, header_style="bold magenta", box=box.ROUNDED)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Phone", style="green")
    table.add_column("Email", style="yellow")
    table.add_column("Address", style="blue")
    
    for contact in contacts:
        name = contact.get('name', 'N/A')
        phone = contact.get('phone', 'N/A')
        email = contact.get('email', 'N/A')
        address = contact.get('address', 'N/A') if contact.get('address') else 'N/A'
        
        table.add_row(name, phone, email, address)
    
    console.print()
    console.print(table)
    console.print(f"\n[dim]Total contacts: {len(contacts)}[/dim]\n")


def display_all_contacts(contacts: List[Dict[str, str]]):
    """Display all contacts."""
    console.print("\n[bold cyan]--- All Contacts ---[/bold cyan]\n")
    display_contacts_table(contacts, title="All Contacts")


def main():
    """Main function to run the contact book application."""
    console.print("\n")
    console.print(Panel.fit(
        "[bold cyan]Welcome to Contact Book Management System[/bold cyan]\n"
        "[dim]Your personal contact organizer[/dim]",
        border_style="cyan"
    ))
    console.print()
    
    # Load existing contacts
    contacts = load_contacts()
    if contacts:
        console.print(f"[green]Loaded {len(contacts)} contact(s) from storage.[/green]\n")
    
    while True:
        display_menu()
        choice = Prompt.ask("[bold]Your choice[/bold]", choices=["1", "2", "3", "4", "5", "6"], default="6")
        
        if choice == "1":
            contacts = add_contact(contacts)
            save_contacts(contacts)
        elif choice == "2":
            search_contact(contacts)
        elif choice == "3":
            contacts = update_contact(contacts)
            save_contacts(contacts)
        elif choice == "4":
            contacts = delete_contact(contacts)
            save_contacts(contacts)
        elif choice == "5":
            display_all_contacts(contacts)
        elif choice == "6":
            console.print("\n[bold green]Thank you for using Contact Book Management System![/bold green]")
            console.print("[dim]Goodbye![/dim]\n")
            break
        
        # Pause before showing menu again
        if choice != "6":
            Prompt.ask("[dim]Press Enter to continue...[/dim]", default="")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Program interrupted by user.[/yellow]")
        console.print("[bold green]Thank you for using Contact Book Management System![/bold green]\n")
    except Exception as e:
        console.print(f"\n[red]An error occurred: {str(e)}[/red]\n")

