
git() {
    # checks if the command arg matches "push"
    if [[ $@ == "push" ]]; then
	# Execute the actual command
	command git push
    else
        command git "$@"
    fi
}
